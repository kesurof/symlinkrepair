import asyncio
import logging
import os

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.cleanup import process_season, process_single
from app.services.config_service import load_config
from app.services.discord import notify_cleanup
from app.services.filescanner import inspect_symlink
from app.services.verifier import get_status as verifier_get_status
from app.services.verifier import remove as verifier_remove
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


async def _sync_siblings(db: Connection, result: dict, new_status: str, new_action: str):
    symlink_path = result.get("symlink_path", "")
    source = result.get("source", "")
    if not symlink_path or not source:
        return
    await db.execute(
        "UPDATE results SET status = ?, action = ?, action_date = datetime('now')"
        " WHERE symlink_path = ? AND source = ? AND id != ?"
        " AND status IN ('détecté', 'recherche', 'en_attente')",
        (new_status, new_action, symlink_path, source, result.get("id", 0)),
    )


@router.get("/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    db: Connection = Depends(get_db),
    source: str = "",
    status: str = "",
    season: str = "",
    q: str = "",
    page: int = 1,
    per_page: int = 50,
    dedup: bool = True,
    scan_id: int = 0,
    group_season: bool = True,
):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50

    where = "WHERE 1=1"
    params = []

    if scan_id:
        where += " AND scan_id = ?"
        params.append(scan_id)
    if source:
        where += " AND source = ?"
        params.append(source)
    if status:
        where += " AND status = ?"
        params.append(status)
    if season:
        where += " AND season = ?"
        params.append(int(season))
    if q:
        where += " AND (media_title LIKE ? OR symlink_path LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    scan_info = None
    if scan_id:
        cursor = await db.execute(
            "SELECT id, source, mode, status, created_at FROM scans WHERE id = ?",
            (scan_id,),
        )
        row = await cursor.fetchone()
        if row:
            scan_info = dict(row)

    r_columns = (
        "r.id, r.source, r.media_title, r.media_type, r.season, r.episode,"
        " r.symlink_path, r.status, r.action, r.search_count, r.series_id, r.file_id"
    )
    columns = (
        "id, source, media_title, media_type, season, episode,"
        " symlink_path, status, action, search_count, series_id, file_id"
    )

    if group_season:
        if dedup:
            cursor = await db.execute(
                f"SELECT {r_columns}, latest.total_count"
                f" FROM results r"
                f" INNER JOIN ("
                f"   SELECT symlink_path, source, MAX(id) as max_id, COUNT(*) as total_count"
                f"   FROM results {where}"
                f"   GROUP BY symlink_path, source"
                f" ) latest ON r.id = latest.max_id"
                f" ORDER BY r.id DESC",
                params,
            )
        else:
            cursor = await db.execute(
                f"SELECT {columns} FROM results {where} ORDER BY id DESC",
                params,
            )
        rows = await cursor.fetchall()
        all_items = [dict(r) for r in rows]

        groups_map: dict[tuple, dict] = {}
        singles = []
        for item in all_items:
            if (
                item.get("source") == "sonarr"
                and item.get("series_id")
                and item.get("season") is not None
            ):
                key = (item["series_id"], item["season"])
                if key not in groups_map:
                    groups_map[key] = {
                        "series_id": item["series_id"],
                        "season": item["season"],
                        "media_title": item["media_title"],
                        "episodes": [],
                    }
                groups_map[key]["episodes"].append(item)
            else:
                singles.append(item)

        display_items = []
        for g in sorted(
            groups_map.values(),
            key=lambda g: max(e["id"] for e in g["episodes"]),
            reverse=True,
        ):
            g["episode_count"] = len(g["episodes"])
            g["replaced_count"] = sum(1 for e in g["episodes"] if e["status"] == "remplacé")
            g["pending_count"] = sum(
                1 for e in g["episodes"] if e["status"] in ("détecté", "recherche")
            )
            g["episodes"].sort(key=lambda e: e.get("episode") or 0)
            for idx, e in enumerate(g["episodes"]):
                if e.get("episode") is None:
                    e["episode"] = (
                        idx + 1 if idx == 0 else g["episodes"][idx - 1].get("episode", idx) + 1
                    )
            display_items.append({"type": "group", **g})

        for s in singles:
            display_items.append({"type": "single", "item": s})

        display_items.sort(
            key=lambda d: (
                max(e["id"] for e in d["episodes"]) if d["type"] == "group" else d["item"]["id"]
            ),
            reverse=True,
        )

        total = len(display_items)
        total_pages = max(1, (total + per_page - 1) // per_page)
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * per_page
        items = display_items[offset : offset + per_page]
        raw_total = len(all_items)
    else:
        if dedup:
            count_cursor = await db.execute(
                f"SELECT COUNT(*) FROM ("
                f"  SELECT MAX(id) FROM results {where} GROUP BY symlink_path, source"
                f" )",
                params,
            )
        else:
            count_cursor = await db.execute(f"SELECT COUNT(*) FROM results {where}", params)
        total = (await count_cursor.fetchone())[0]

        total_pages = max(1, (total + per_page - 1) // per_page)
        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        if dedup:
            cursor = await db.execute(
                f"SELECT {r_columns}, latest.total_count"
                f" FROM results r"
                f" INNER JOIN ("
                f"   SELECT symlink_path, source, MAX(id) as max_id, COUNT(*) as total_count"
                f"   FROM results {where}"
                f"   GROUP BY symlink_path, source"
                f" ) latest ON r.id = latest.max_id"
                f" ORDER BY r.id DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            )
        else:
            cursor = await db.execute(
                f"SELECT {columns} FROM results {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            )
        rows = await cursor.fetchall()
        items = [dict(r) for r in rows]
        raw_total = total

    cursor_src = await db.execute("SELECT DISTINCT source FROM results")
    sources = [r[0] for r in await cursor_src.fetchall()]
    cursor_st = await db.execute("SELECT DISTINCT status FROM results")
    statuses = [r[0] for r in await cursor_st.fetchall()]

    is_htmx = request.headers.get("hx-request") == "true"
    template = "partials/results_content.html" if is_htmx else "results.html"

    copy_icon = (
        '<svg class="w-4 h-4 text-gray-400 dark:text-gray-500 hover:text-gray-600 '
        'dark:hover:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" '
        'stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" '
        'd="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 '
        "1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 "
        "01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 "
        "1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 "
        '014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/>'
        "</svg>"
    )

    return templates.TemplateResponse(
        request,
        template,
        {
            "items": items,
            "sources": sources,
            "statuses": statuses,
            "active_source": source,
            "active_status": status,
            "active_season": season,
            "active_q": q,
            "active_scan_id": scan_id,
            "scan_info": scan_info,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "show_duplicates": not dedup,
            "group_season": group_season,
            "raw_total": raw_total,
            "copy_icon": copy_icon,
        },
    )


@router.get("/api/results/ids")
async def results_ids(
    db: Connection = Depends(get_db),
    source: str = "",
    status: str = "",
    season: str = "",
    q: str = "",
    dedup: bool = True,
    scan_id: int = 0,
):
    where = "WHERE 1=1"
    params = []
    if scan_id:
        where += " AND scan_id = ?"
        params.append(scan_id)
    if source:
        where += " AND source = ?"
        params.append(source)
    if status:
        where += " AND status = ?"
        params.append(status)
    if season:
        where += " AND season = ?"
        params.append(int(season))
    if q:
        where += " AND (media_title LIKE ? OR symlink_path LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    if dedup:
        cursor = await db.execute(
            f"SELECT MAX(id) as id FROM results {where} GROUP BY symlink_path, source ORDER BY id",
            params,
        )
    else:
        cursor = await db.execute(f"SELECT id FROM results {where} ORDER BY id", params)
    rows = await cursor.fetchall()
    return {"ids": [r[0] for r in rows]}


@router.get("/api/results/recent")
async def recent_results(db: Connection = Depends(get_db), limit: int = 5):
    cursor = await db.execute(
        "SELECT id, source, media_title, symlink_path, status"
        " FROM results WHERE status IN ('détecté','recherche')"
        " ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return {"results": [dict(r) for r in await cursor.fetchall()]}


@router.get("/results/{result_id}", response_class=HTMLResponse)
async def result_detail(request: Request, result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    return templates.TemplateResponse(request, "detail.html", {"item": dict(row)})


@router.post("/api/results/{result_id}/ignore")
async def ignore_result(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, symlink_path, source FROM results WHERE id = ?", (result_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)
    result = dict(row)
    await db.execute(
        "UPDATE results SET status = 'ignoré', action = 'ignored',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await _sync_siblings(db, result, "ignoré", "ignored_sibling")
    await db.commit()
    logger.info("Result %d ignored", result_id)
    return {"ok": True}


@router.post("/api/results/{result_id}/recheck")
async def recheck_result(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, symlink_path, source FROM results WHERE id = ?", (result_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)
    result = dict(row)
    await db.execute(
        "UPDATE results SET status = 'recherche', action = 'recheck',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await _sync_siblings(db, result, "recherche", "recheck_sibling")
    await db.commit()
    logger.info("Result %d recheck scheduled", result_id)
    return {"ok": True}


@router.post("/api/results/{result_id}/fix")
async def fix_result(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, symlink_path, source FROM results WHERE id = ?", (result_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)
    result = dict(row)
    await db.execute(
        "UPDATE results SET status = 'remplacé', action = 'manual_fix',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await _sync_siblings(db, result, "remplacé", "manual_fix_sibling")
    await db.commit()
    logger.info("Result %d fixed (manual)", result_id)
    return {"ok": True}


@router.get("/api/results/{result_id}/verifier")
async def verifier_status(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT symlink_path FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)
    status = verifier_get_status(row["symlink_path"])
    if not status:
        return {"ok": True, "pending": False}
    return {"ok": True, **status}


@router.post("/api/results/{result_id}/stop-verifier")
async def stop_verifier(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, symlink_path, source FROM results WHERE id = ?", (result_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)
    result = dict(row)
    removed = verifier_remove(result["symlink_path"])
    if removed:
        await db.execute(
            "UPDATE results SET status = 'non_remplacé', action = 'abandon',"
            " action_date = datetime('now') WHERE id = ?",
            (result_id,),
        )
        await _sync_siblings(db, result, "non_remplacé", "abandon_sibling")
        await db.commit()
        logger.info("Result %d verifier stopped (abandon)", result_id)
    return {"ok": True}


@router.post("/api/results/{result_id}/verify-fs")
async def verify_filesystem(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)

    result = dict(row)
    path = result.get("symlink_path", "")
    if not path or not os.path.islink(path):
        return {
            "ok": True,
            "valid": False,
            "reason": "Le symlink n'existe plus",
            "status_updated": False,
        }

    config = load_config()
    cfg_sources = {"radarr": config.radarr, "sonarr": config.sonarr}
    cfg = cfg_sources.get(result.get("source", ""))
    if not cfg:
        return {"ok": True, "valid": False, "reason": "Source inconnue", "status_updated": False}

    info = inspect_symlink(path, cfg.target_prefixes)
    if info.get("broken"):
        return {
            "ok": True,
            "valid": False,
            "reason": "Le symlink est toujours cassé",
            "status_updated": False,
        }

    valid = info.get("exists", False) and info.get("matches_prefix", False)
    if valid:
        await db.execute(
            "UPDATE results SET status = 'remplacé', action = 'verify_fs',"
            " action_date = datetime('now') WHERE id = ?",
            (result_id,),
        )
        await _sync_siblings(db, result, "remplacé", "verify_fs_sibling")
        await db.commit()
        logger.info("Result %d: verified on filesystem, marked as replaced", result_id)
        return {"ok": True, "valid": True, "status_updated": True, "status": "remplacé"}

    return {
        "ok": True,
        "valid": False,
        "reason": "La cible ne correspond pas aux préfixes autorisés",
        "status_updated": False,
    }


@router.post("/api/results/{result_id}/process")
async def process_single_result(
    result_id: int, delete_season: bool = False, db: Connection = Depends(get_db)
):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)

    result = dict(row)
    scan_id = result.get("scan_id")

    if delete_season and result.get("source") == "sonarr":
        outcome = await process_season(result, db, scan_id)
    else:
        outcome = await process_single(result)

        if outcome.get("auto_fixed"):
            await db.execute(
                "UPDATE results SET status = 'remplacé', action = 'auto_fix',"
                " action_date = datetime('now') WHERE id = ?",
                (result_id,),
            )
            await _sync_siblings(db, result, "remplacé", "auto_fix_sibling")
            await db.commit()
            logger.info("Result %d auto-fixed (symlink already valid)", result_id)
        elif outcome["ok"]:
            await db.execute(
                "UPDATE results SET status = 'en_attente', action = 'api_delete',"
                " search_count = search_count + 1, action_date = datetime('now') WHERE id = ?",
                (result_id,),
            )
            await _sync_siblings(db, result, "en_attente", "api_delete_sibling")
            await db.commit()

    config = load_config()
    await notify_cleanup(config, result, outcome.get("actions", {}))

    logger.info(
        "Result %d processed: ok=%s error=%s delete_season=%s",
        result_id,
        outcome.get("ok"),
        outcome.get("error", ""),
        delete_season,
    )
    return outcome


@router.post("/api/results/batch")
async def batch_action(request: Request, db: Connection = Depends(get_db)):
    body = await request.json()
    action = body.get("action", "")
    ids = body.get("ids", [])

    if action in ("process_season", "verify_season"):
        series_id = body.get("series_id")
        season_num = body.get("season")
        if not series_id or season_num is None:
            return JSONResponse(
                {"ok": False, "error": "series_id et season requis"}, status_code=400
            )
        cursor_ps = await db.execute(
            "SELECT * FROM results"
            " WHERE series_id = ? AND season = ? AND source = 'sonarr' LIMIT 1",
            (series_id, season_num),
        )
        row_ps = await cursor_ps.fetchone()
        if not row_ps:
            return JSONResponse(
                {"ok": False, "error": "Aucun résultat trouvé pour cette saison"},
                status_code=404,
            )

        if action == "process_season":
            result_ps = dict(row_ps)
            outcome_ps = await process_season(result_ps, db, result_ps.get("scan_id", 0))
            return {
                "ok": outcome_ps.get("ok", False),
                "affected": outcome_ps.get("processed", 0),
                "total": outcome_ps.get("total", 0),
            }

        if action == "verify_season":
            rows_ps = await db.execute(
                "SELECT id, symlink_path, source, status FROM results"
                " WHERE series_id = ? AND season = ? AND source = 'sonarr'",
                (series_id, season_num),
            )
            all_rows = await rows_ps.fetchall()
            config = load_config()
            cfg_sources = {"radarr": config.radarr, "sonarr": config.sonarr}
            verified = 0
            for r in all_rows:
                rdict = dict(r)
                path = rdict.get("symlink_path", "")
                if not path or not os.path.islink(path):
                    continue
                cfg = cfg_sources.get(rdict.get("source", ""))
                if not cfg:
                    continue
                info = inspect_symlink(path, cfg.target_prefixes)
                valid = info.get("exists", False) and info.get("matches_prefix", False)
                if valid:
                    await db.execute(
                        "UPDATE results SET status = 'remplacé', action = 'verify_fs',"
                        " action_date = datetime('now') WHERE id = ?",
                        (rdict["id"],),
                    )
                    verified += 1
            await db.commit()
            logger.info(
                "Season verify: series=%s season=%s verified=%d total=%d",
                series_id,
                season_num,
                verified,
                len(all_rows),
            )
            return {"ok": True, "verified": verified, "total": len(all_rows)}

    if not ids:
        return JSONResponse({"ok": False, "error": "Aucun ID fourni"}, status_code=400)

    if action == "ignore":
        placeholders = ",".join("?" for _ in ids)
        await db.execute(
            f"UPDATE results SET status = 'ignoré', action = 'ignored',"
            f" action_date = datetime('now') WHERE id IN ({placeholders})",
            ids,
        )
        await db.execute(
            f"UPDATE results SET status = 'ignoré', action = 'ignored_sibling',"
            f" action_date = datetime('now')"
            f" WHERE (symlink_path, source) IN ("
            f"   SELECT symlink_path, source FROM results WHERE id IN ({placeholders})"
            f" ) AND id NOT IN ({placeholders})"
            f" AND status IN ('détecté','recherche','en_attente')",
            ids + ids + ids,
        )
        await db.commit()
        affected = len(ids)
    elif action == "fix":
        placeholders = ",".join("?" for _ in ids)
        await db.execute(
            f"UPDATE results SET status = 'remplacé', action = 'manual_fix',"
            f" action_date = datetime('now') WHERE id IN ({placeholders})",
            ids,
        )
        await db.execute(
            f"UPDATE results SET status = 'remplacé', action = 'manual_fix_sibling',"
            f" action_date = datetime('now')"
            f" WHERE (symlink_path, source) IN ("
            f"   SELECT symlink_path, source FROM results WHERE id IN ({placeholders})"
            f" ) AND id NOT IN ({placeholders})"
            f" AND status IN ('détecté','recherche','en_attente')",
            ids + ids + ids,
        )
        await db.commit()
        affected = len(ids)
    elif action == "delete":
        placeholders = ",".join("?" for _ in ids)
        await db.execute(f"DELETE FROM results WHERE id IN ({placeholders})", ids)
        await db.commit()
        affected = len(ids)
    elif action == "process":
        config = load_config()
        ok_count = 0
        delete_season = body.get("delete_season", False)
        for rid in ids:
            cursor = await db.execute("SELECT * FROM results WHERE id = ?", (rid,))
            row = await cursor.fetchone()
            if not row:
                continue
            result = dict(row)
            if (
                delete_season
                and result.get("source") == "sonarr"
                and result.get("series_id")
                and result.get("season") is not None
            ):
                outcome = await process_season(result, db, 0)
            else:
                outcome = await process_single(result)
            if outcome.get("auto_fixed"):
                ok_count += 1
                await db.execute(
                    "UPDATE results SET status = 'remplacé', action = 'auto_fix',"
                    " action_date = datetime('now') WHERE id = ?",
                    (rid,),
                )
                await _sync_siblings(db, result, "remplacé", "auto_fix_sibling")
                await db.commit()
            elif outcome.get("ok"):
                ok_count += 1
                await db.execute(
                    "UPDATE results SET status = 'en_attente', action = 'api_delete',"
                    " search_count = search_count + 1, action_date = datetime('now') WHERE id = ?",
                    (rid,),
                )
                await _sync_siblings(db, result, "en_attente", "api_delete_sibling")
                await db.commit()
                await notify_cleanup(config, result, outcome.get("actions", {}))
            await asyncio.sleep(0.1)
        affected = ok_count
    elif action == "recheck":
        placeholders = ",".join("?" for _ in ids)
        await db.execute(
            f"UPDATE results SET status = 'recherche', action = 'recheck',"
            f" action_date = datetime('now') WHERE id IN ({placeholders})",
            ids,
        )
        await db.execute(
            f"UPDATE results SET status = 'recherche', action = 'recheck_sibling',"
            f" action_date = datetime('now')"
            f" WHERE (symlink_path, source) IN ("
            f"   SELECT symlink_path, source FROM results WHERE id IN ({placeholders})"
            f" ) AND id NOT IN ({placeholders})"
            f" AND status IN ('détecté','recherche','en_attente')",
            ids + ids + ids,
        )
        await db.commit()
        affected = len(ids)
    else:
        return JSONResponse({"ok": False, "error": f"Action inconnue: {action}"}, status_code=400)

    logger.info("Batch %s: %d results affected", action, affected)
    return {"ok": True, "affected": affected}
