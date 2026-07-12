import asyncio
import logging

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.alldebrid import AllDebridAPI, is_hash_name
from app.services.config_service import browse_directory, load_config
from app.services.filescanner import analyze_symlink_targets
from app.services.orphan_detector import OrphanDetector
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


def _collect_fallback_prefixes(config) -> list[str]:
    prefixes = set()
    for src in (config.radarr, config.sonarr):
        prefixes.update(src.target_prefixes)
    return list(prefixes)


async def _compute_stats(db: Connection) -> dict:
    cursor = await db.execute("SELECT COUNT(*) FROM orphan_magnets")
    total_magnets = (await cursor.fetchone())[0]
    cursor = await db.execute("SELECT COUNT(*) FROM orphan_magnets WHERE status = 'orphan'")
    orphan_count = (await cursor.fetchone())[0]
    cursor = await db.execute("SELECT COUNT(*) FROM orphan_magnets WHERE status = 'used'")
    used_count = (await cursor.fetchone())[0]
    cursor = await db.execute("SELECT COUNT(*) FROM orphan_magnets WHERE status = 'protected'")
    protected_count = (await cursor.fetchone())[0]
    return {
        "total_magnets": total_magnets,
        "orphan_count": orphan_count,
        "used_count": used_count,
        "protected_count": protected_count,
    }


@router.get("/orphans", response_class=HTMLResponse)
async def orphans_page(request: Request, db: Connection = Depends(get_db)):
    config = load_config()
    ad = config.alldebrid
    configured = any(inst.enabled and inst.api_key and inst.library_roots for inst in ad.instances)

    stats = await _compute_stats(db)

    instance_names = [i.name for i in ad.instances if i.name]

    return templates.TemplateResponse(
        request,
        "orphans.html",
        {
            "configured": configured,
            "schedule_time": ad.schedule_time,
            "instance_names": instance_names,
            **stats,
        },
    )


async def _build_content_query(q: str, page: int, per_page: int, db: Connection):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 50

    where = "WHERE status = 'orphan'"
    params = []

    if q:
        where += " AND (primary_name LIKE ? OR magnet_id LIKE ? OR notes LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])

    count_cursor = await db.execute(f"SELECT COUNT(*) FROM orphan_magnets {where}", params)
    total = (await count_cursor.fetchone())[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    cursor = await db.execute(
        f"SELECT id, magnet_id, primary_name, status, age_hours, is_hash,"
        f" action, action_date, created_at, notes"
        f" FROM orphan_magnets {where}"
        f" ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )
    rows = await cursor.fetchall()
    magnets = [dict(r) for r in rows]

    return {
        "magnets": magnets,
        "active_q": q,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }


@router.get("/api/orphans/content")
async def orphans_content(
    request: Request,
    db: Connection = Depends(get_db),
    q: str = "",
    page: int = 1,
    per_page: int = 50,
):
    ctx = await _build_content_query(q, page, per_page, db)

    is_htmx = request.headers.get("hx-request") == "true"
    template = "partials/orphans_content.html" if is_htmx else "orphans.html"

    return templates.TemplateResponse(request, template, ctx)


@router.post("/api/orphans/scan")
async def run_orphan_scan(
    request: Request,
    db: Connection = Depends(get_db),
    instance: str = Form(""),
):
    config = load_config()
    ad = config.alldebrid
    is_htmx = request.headers.get("hx-request") == "true"

    if instance:
        enabled = [
            i
            for i in ad.instances
            if i.name == instance and i.enabled and i.api_key and i.library_roots
        ]
        if not enabled:
            return JSONResponse(
                {"ok": False, "error": f"Instance «{instance}» introuvable ou inactive"},
                status_code=400,
            )
    else:
        enabled = [i for i in ad.instances if i.enabled and i.api_key and i.library_roots]

    if not enabled:
        return JSONResponse(
            {"ok": False, "error": "Aucune instance AllDebrid active configurée"},
            status_code=400,
        )

    await db.execute("DELETE FROM orphan_magnets")
    await db.commit()

    fallback = _collect_fallback_prefixes(config)
    results = []
    total_orphans = 0
    total_magnets = 0

    for inst in enabled:
        detector = OrphanDetector(inst, fallback_prefixes=fallback)
        try:
            result = await detector.run()
        except Exception as e:
            logger.error("Orphan scan failed for %s: %s", inst.name, e)
            return JSONResponse(
                {"ok": False, "error": f"{inst.name}: {e}"},
                status_code=500,
            )
        for cand in result.orphans + result.protected + result.used:
            await db.execute(
                "INSERT INTO orphan_magnets"
                " (magnet_id, primary_name, status, age_hours, is_hash, notes)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    cand.magnet_id,
                    cand.primary_name,
                    cand.status,
                    cand.age_hours,
                    1 if is_hash_name(cand.primary_name) else 0,
                    inst.name,
                ),
            )
        results.append(result)
        total_orphans += result.orphan_count
        total_magnets += result.total_magnets

    await db.commit()

    if is_htmx:
        stats = await _compute_stats(db)
        ctx = await _build_content_query("", 1, 50, db)
        ctx.update(stats)
        ctx["scan_ok"] = True
        ctx["scan_instances"] = [
            {
                "name": r.instance_name,
                "total_magnets": r.total_magnets,
                "used": r.used_count,
                "protected": r.protected_count,
                "orphans": r.orphan_count,
                "duration": round(r.duration, 1),
            }
            for r in results
        ]
        ctx["scan_orphan_count"] = total_orphans
        ctx["oob_stats"] = True
        return templates.TemplateResponse(
            request,
            "partials/orphans_content.html",
            ctx,
        )

    return {
        "ok": True,
        "total_magnets": total_magnets,
        "orphan_count": total_orphans,
        "instances": [
            {
                "name": r.instance_name,
                "total_magnets": r.total_magnets,
                "used": r.used_count,
                "protected": r.protected_count,
                "orphans": r.orphan_count,
                "duration": round(r.duration, 1),
            }
            for r in results
        ],
    }


@router.post("/api/orphans/delete-instance")
async def delete_instance_orphans(
    request: Request,
    db: Connection = Depends(get_db),
    instance_name: str = Form(""),
):
    config = load_config()
    is_htmx = request.headers.get("hx-request") == "true"

    cursor = await db.execute(
        "SELECT id, magnet_id FROM orphan_magnets WHERE status = 'orphan' AND notes = ?",
        (instance_name,),
    )
    rows = await cursor.fetchall()
    if not rows:
        if is_htmx:
            stats = await _compute_stats(db)
            ctx = await _build_content_query("", 1, 50, db)
            ctx.update(stats)
            ctx["oob_stats"] = True
            return templates.TemplateResponse(
                request,
                "partials/orphans_content.html",
                ctx,
            )
        return {"ok": True, "deleted": 0, "errors": 0}

    magnets = [dict(r) for r in rows]

    inst = next(
        (i for i in config.alldebrid.instances if i.name == instance_name and i.api_key),
        None,
    )
    if not inst:
        return JSONResponse(
            {"ok": False, "error": f"Instance {instance_name} introuvable ou inactive"},
            status_code=400,
        )

    deleted = 0
    errors = 0
    async with AllDebridAPI(inst.api_key, inst.rate_limit) as api:
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

    if is_htmx:
        stats = await _compute_stats(db)
        ctx = await _build_content_query("", 1, 50, db)
        ctx.update(stats)
        ctx["oob_stats"] = True
        return templates.TemplateResponse(
            request,
            "partials/orphans_content.html",
            ctx,
        )


@router.post("/api/orphans/analyze-symlinks")
async def analyze_symlinks(request: Request, path: str = Form(...)):
    config = load_config()
    result = browse_directory(path, config.browse_roots)
    if result is None:
        return JSONResponse(
            {"ok": False, "error": "Chemin non autorisé ou invalide"},
            status_code=400,
        )

    data = await asyncio.to_thread(analyze_symlink_targets, path)
    data["ok"] = True
    return data
