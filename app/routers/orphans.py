import logging

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.alldebrid import AllDebridAPI, is_hash_name
from app.services.config_service import load_config
from app.services.orphan_detector import OrphanDetector
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


def _collect_prefixes(config) -> list[str]:
    prefixes = set()
    for src in (config.radarr, config.sonarr):
        prefixes.update(src.target_prefixes)
    return list(prefixes)


async def _store_scan(db: Connection, detector_result, mode: str) -> int:
    cursor = await db.execute(
        "INSERT INTO scans (source, mode, status, total, broken, processed, summary, completed_at)"
        " VALUES (?, ?, ?, ?, ?, 0, ?, datetime('now'))",
        (
            "alldebrid",
            mode,
            "completed",
            detector_result.total_magnets,
            detector_result.orphan_count,
            (
                f"{detector_result.used_count} used,"
                f" {detector_result.protected_count} protected,"
                f" {detector_result.orphan_count} orphans"
            ),
        ),
    )
    scan_id = cursor.lastrowid

    for cand in detector_result.orphans + detector_result.protected + detector_result.used:
        await db.execute(
            "INSERT INTO orphan_magnets"
            " (scan_id, magnet_id, primary_name, status, age_hours, is_hash)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                cand.magnet_id,
                cand.primary_name,
                cand.status,
                cand.age_hours,
                1 if is_hash_name(cand.primary_name) else 0,
            ),
        )
    return scan_id


@router.get("/orphans", response_class=HTMLResponse)
async def orphans_page(request: Request, db: Connection = Depends(get_db)):
    config = load_config()
    ad = config.alldebrid
    configured = bool(ad.api_key and ad.medias_base)

    cursor = await db.execute(
        "SELECT COUNT(*) FROM orphan_magnets WHERE status = 'orphan'"
    )
    orphan_count = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT id, status, total, broken, processed, created_at"
        " FROM scans WHERE source = 'alldebrid'"
        " ORDER BY id DESC LIMIT 5"
    )
    recent_scans = [dict(r) for r in await cursor.fetchall()]

    return templates.TemplateResponse(
        request,
        "orphans.html",
        {
            "configured": configured,
            "orphan_count": orphan_count,
            "recent_scans": recent_scans,
            "medias_base": ad.medias_base,
            "schedule_time": ad.schedule_time,
            "min_age_hours": ad.min_age_hours,
        },
    )


@router.get("/api/orphans/content")
async def orphans_content(
    request: Request,
    db: Connection = Depends(get_db),
    status: str = "",
    q: str = "",
    page: int = 1,
    per_page: int = 50,
):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50

    where = "WHERE 1=1"
    params = []

    if status:
        where += " AND status = ?"
        params.append(status)
    if q:
        where += " AND (primary_name LIKE ? OR magnet_id LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    count_cursor = await db.execute(
        f"SELECT COUNT(*) FROM orphan_magnets {where}", params
    )
    total = (await count_cursor.fetchone())[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    cursor = await db.execute(
        f"SELECT id, magnet_id, primary_name, status, age_hours, is_hash,"
        f" action, action_date, created_at"
        f" FROM orphan_magnets {where}"
        f" ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )
    rows = await cursor.fetchall()
    magnets = [dict(r) for r in rows]

    is_htmx = request.headers.get("hx-request") == "true"
    template = "partials/orphans_content.html" if is_htmx else "orphans.html"

    return templates.TemplateResponse(
        request,
        template,
        {
            "magnets": magnets,
            "active_status": status,
            "active_q": q,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.post("/api/orphans/scan")
async def run_orphan_scan(db: Connection = Depends(get_db)):
    config = load_config()
    ad = config.alldebrid

    if not ad.api_key:
        return JSONResponse(
            {"ok": False, "error": "Clé API AllDebrid non configurée"}, status_code=400)
    if not ad.medias_base:
        return JSONResponse(
            {"ok": False, "error": "medias_base non configuré"}, status_code=400)

    prefixes = _collect_prefixes(config)
    if not prefixes:
        return JSONResponse(
            {"ok": False, "error": "Aucun target_prefixes configuré (Radarr/Sonarr)"},
            status_code=400)

    detector = OrphanDetector(
        medias_base=ad.medias_base,
        target_prefixes=list(set(prefixes)),
        api_key=ad.api_key,
        min_age_hours=ad.min_age_hours,
        rate_limit=ad.rate_limit,
    )

    try:
        result = await detector.run()
    except Exception as e:
        logger.error("Orphan scan failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    scan_id = await _store_scan(db, result, "manual")
    await db.commit()

    return {
        "ok": True,
        "scan_id": scan_id,
        "total_magnets": result.total_magnets,
        "used_count": result.used_count,
        "protected_count": result.protected_count,
        "orphan_count": result.orphan_count,
        "duration": round(result.duration, 1),
    }


@router.post("/api/orphans/delete-all")
async def delete_all_orphans(db: Connection = Depends(get_db)):
    config = load_config()
    ad = config.alldebrid
    if not ad.api_key:
        return JSONResponse({"ok": False, "error": "Clé API non configurée"}, status_code=400)

    cursor = await db.execute(
        "SELECT id, magnet_id, primary_name FROM orphan_magnets WHERE status = 'orphan'"
    )
    rows = await cursor.fetchall()
    if not rows:
        return {"ok": True, "deleted": 0, "errors": 0}

    magnets = [dict(r) for r in rows]
    deleted = 0
    errors = 0

    async with AllDebridAPI(ad.api_key, ad.rate_limit) as api:
        for m in magnets:
            try:
                ok = await api.delete_magnet(m["magnet_id"])
                if ok:
                    deleted += 1
                    await db.execute(
                        "UPDATE orphan_magnets SET status = 'supprimé', action = 'deleted',"
                        " action_date = datetime('now') WHERE id = ?",
                        (m["id"],),
                    )
            except Exception as e:
                logger.warning("Delete failed for %s: %s", m["magnet_id"], e)
                errors += 1

    await db.commit()
    return {"ok": True, "deleted": deleted, "errors": errors}


@router.post("/api/orphans/{magnet_id}/delete")
async def delete_orphan(magnet_id: int, db: Connection = Depends(get_db)):
    config = load_config()
    ad = config.alldebrid
    if not ad.api_key:
        return JSONResponse({"ok": False, "error": "Clé API non configurée"}, status_code=400)

    cursor = await db.execute(
        "SELECT id, magnet_id, primary_name FROM orphan_magnets WHERE id = ?", (magnet_id,)
    )
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Magnét introuvable"}, status_code=404)
    m = dict(row)

    async with AllDebridAPI(ad.api_key, ad.rate_limit) as api:
        ok = await api.delete_magnet(m["magnet_id"])

    if ok:
        await db.execute(
            "UPDATE orphan_magnets SET status = 'supprimé', action = 'deleted',"
            " action_date = datetime('now') WHERE id = ?",
            (m["id"],),
        )
        await db.commit()
        return {"ok": True}
    return JSONResponse({"ok": False, "error": "Échec de la suppression"}, status_code=500)


@router.post("/api/orphans/{magnet_id}/ignore")
async def ignore_orphan(magnet_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id FROM orphan_magnets WHERE id = ?", (magnet_id,)
    )
    if not await cursor.fetchone():
        return JSONResponse({"ok": False, "error": "Magnét introuvable"}, status_code=404)

    await db.execute(
        "UPDATE orphan_magnets SET status = 'ignoré', action = 'ignored',"
        " action_date = datetime('now') WHERE id = ?",
        (magnet_id,),
    )
    await db.commit()
    return {"ok": True}


@router.post("/api/orphans/batch")
async def batch_orphan_action(request: Request, db: Connection = Depends(get_db)):
    body = await request.json()
    action = body.get("action", "")
    ids = body.get("ids", [])

    if action not in ("delete", "ignore"):
        return JSONResponse({"ok": False, "error": "Action invalide"}, status_code=400)

    if action == "ignore":
        placeholders = ",".join("?" for _ in ids)
        await db.execute(
            f"UPDATE orphan_magnets SET status = 'ignoré', action = 'ignored',"
            f" action_date = datetime('now') WHERE id IN ({placeholders})",
            ids,
        )
        await db.commit()
        return {"ok": True, "affected": len(ids)}

    if action == "delete":
        config = load_config()
        ad = config.alldebrid
        if not ad.api_key:
            return JSONResponse({"ok": False, "error": "Clé API non configurée"}, status_code=400)

        placeholders = ",".join("?" for _ in ids)
        cursor = await db.execute(
            f"SELECT id, magnet_id FROM orphan_magnets WHERE id IN ({placeholders})", ids
        )
        rows = [dict(r) for r in await cursor.fetchall()]

        deleted = 0
        async with AllDebridAPI(ad.api_key, ad.rate_limit) as api:
            for m in rows:
                try:
                    ok = await api.delete_magnet(m["magnet_id"])
                    if ok:
                        deleted += 1
                        await db.execute(
                            "UPDATE orphan_magnets SET status = 'supprimé', action = 'deleted',"
                            " action_date = datetime('now') WHERE id = ?",
                            (m["id"],),
                        )
                except Exception as e:
                    logger.warning("Batch delete failed for %s: %s", m["magnet_id"], e)

        await db.commit()
        return {"ok": True, "deleted": deleted, "total": len(rows)}


@router.get("/api/orphans/stats")
async def orphans_stats(db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT"
        " (SELECT COUNT(*) FROM orphan_magnets) AS total,"
        " (SELECT COUNT(*) FROM orphan_magnets WHERE status = 'orphan') AS orphan_count,"
        " (SELECT COUNT(*) FROM orphan_magnets WHERE status = 'used') AS used_count,"
        " (SELECT COUNT(*) FROM orphan_magnets WHERE status = 'protected') AS protected_count,"
        " (SELECT COUNT(*) FROM orphan_magnets WHERE status = 'supprimé') AS deleted_count"
    )
    stats = dict(await cursor.fetchone())

    cursor = await db.execute(
        "SELECT id, status, total, broken, processed, created_at"
        " FROM scans WHERE source = 'alldebrid'"
        " ORDER BY id DESC LIMIT 1"
    )
    last = await cursor.fetchone()
    stats["last_scan"] = dict(last) if last else None
    return stats
