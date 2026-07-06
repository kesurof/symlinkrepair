import asyncio
import logging

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.cleanup import process_season, process_single
from app.services.config_service import load_config
from app.services.discord import notify_cleanup
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


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
):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50

    where = "WHERE 1=1"
    params = []

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
            f"SELECT r.id, r.source, r.media_title, r.media_type, r.season,"
            f" r.symlink_path, r.status, r.action, latest.total_count"
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
            f"SELECT id, source, media_title, media_type, season,"
            f" symlink_path, status, action"
            f" FROM results {where}"
            f" ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset],
        )
    rows = await cursor.fetchall()
    items = [dict(r) for r in rows]

    cursor_src = await db.execute("SELECT DISTINCT source FROM results")
    sources = [r[0] for r in await cursor_src.fetchall()]
    cursor_st = await db.execute("SELECT DISTINCT status FROM results")
    statuses = [r[0] for r in await cursor_st.fetchall()]

    is_htmx = request.headers.get("hx-request") == "true"
    template = "partials/results_content.html" if is_htmx else "results.html"

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
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "show_duplicates": not dedup,
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
):
    where = "WHERE 1=1"
    params = []
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


@router.get("/results/{result_id}", response_class=HTMLResponse)
async def result_detail(request: Request, result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    return templates.TemplateResponse(request, "detail.html", {"item": dict(row)})


@router.post("/api/results/{result_id}/ignore")
async def ignore_result(result_id: int, db: Connection = Depends(get_db)):
    await db.execute(
        "UPDATE results SET status = 'ignoré', action = 'ignored',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    logger.info("Result %d ignored", result_id)
    return {"ok": True}


@router.post("/api/results/{result_id}/recheck")
async def recheck_result(result_id: int, db: Connection = Depends(get_db)):
    await db.execute(
        "UPDATE results SET status = 'recherche', action = NULL, action_date = NULL WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    logger.info("Result %d recheck_needed", result_id)
    return {"ok": True}


@router.post("/api/results/{result_id}/fix")
async def fix_result(result_id: int, db: Connection = Depends(get_db)):
    await db.execute(
        "UPDATE results SET status = 'réparé', action = 'manual_fix',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    logger.info("Result %d fixed (manual)", result_id)
    return {"ok": True}


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

        if outcome["ok"]:
            await db.execute(
                "UPDATE results SET status = 'en_attente', action = 'api_delete',"
                " action_date = datetime('now') WHERE id = ?",
                (result_id,),
            )
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

    if not ids:
        return JSONResponse({"ok": False, "error": "Aucun ID fourni"}, status_code=400)

    if action == "ignore":
        await db.execute(
            f"UPDATE results SET status = 'ignoré', action = 'ignored',"
            f" action_date = datetime('now') WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
        await db.commit()
        affected = len(ids)
    elif action == "fix":
        await db.execute(
            f"UPDATE results SET status = 'réparé', action = 'manual_fix',"
            f" action_date = datetime('now') WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
        await db.commit()
        affected = len(ids)
    elif action == "recheck":
        await db.execute(
            f"UPDATE results SET status = 'recherche',"
            f" action = NULL, action_date = NULL WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
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
        for rid in ids:
            cursor = await db.execute("SELECT * FROM results WHERE id = ?", (rid,))
            row = await cursor.fetchone()
            if not row:
                continue
            result = dict(row)
            outcome = await process_single(result)
            if outcome["ok"]:
                ok_count += 1
                await db.execute(
                    "UPDATE results SET status = 'en_attente', action = 'api_delete',"
                    " action_date = datetime('now') WHERE id = ?",
                    (rid,),
                )
                await db.commit()
                await notify_cleanup(config, result, outcome.get("actions", {}))
            await asyncio.sleep(0.1)
        affected = ok_count
    else:
        return JSONResponse({"ok": False, "error": f"Action inconnue: {action}"}, status_code=400)

    logger.info("Batch %s: %d results affected", action, affected)
    return {"ok": True, "affected": affected}
