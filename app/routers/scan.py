import logging
from datetime import datetime

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.database import get_db
from app.services import filescanner, scanner
from app.services.cleanup import process_all_detected
from app.services.config_service import load_config
from app.services.discord import notify_scan
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request, db: Connection = Depends(get_db)):
    config = load_config()
    cursor = await db.execute(
        "SELECT id, source, mode, status, broken, created_at FROM scans ORDER BY id DESC LIMIT 5"
    )
    recent_scans = [dict(r) for r in await cursor.fetchall()]
    return templates.TemplateResponse(
        request, "scan.html", {"default_limit": config.defaults.limit, "recent_scans": recent_scans}
    )


@router.post("/api/scan/{source}")
async def trigger_scan(
    source: str, mode: str = "simulate", limit: int = 0, db: Connection = Depends(get_db)
):
    if source not in ("radarr", "sonarr"):
        return JSONResponse({"error": "source invalide"}, status_code=400)

    logger.info("Scan triggered: source=%s mode=%s limit=%d", source, mode, limit)
    result = await scanner.start_scan(source, mode, limit)
    if result["status"] == "error":
        logger.warning("Scan failed: source=%s error=%s", source, result.get("error"))
        return JSONResponse(result, status_code=409)

    # Store scan in DB
    cursor = await db.execute(
        "INSERT INTO scans (source, mode, status, total, broken, processed, summary, completed_at)"
        " VALUES (?, ?, ?, ?, ?, 0, ?, datetime('now'))",
        (
            source,
            mode,
            result["status"],
            result.get("total", 0),
            result.get("broken", 0),
            "",
        ),
    )
    scan_id = cursor.lastrowid

    # Store results with dedup
    inserted = 0
    for target in result.get("targets", []):
        existing = await db.execute(
            "SELECT id FROM results WHERE symlink_path = ? AND source = ?"
            " AND status IN ('détecté', 'surveillance') LIMIT 1",
            (target.get("symlink_path", ""), target.get("source", source)),
        )
        if await existing.fetchone():
            continue
        await db.execute(
            "INSERT INTO results (scan_id, source, symlink_path, target_path,"
            " media_type, media_title, season, episode, file_id, movie_id, series_id,"
            " tags, detection, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                target.get("source", source),
                target.get("symlink_path", ""),
                target.get("target_path", ""),
                target.get("media_type"),
                target.get("media_title"),
                target.get("season"),
                target.get("episode"),
                target.get("file_id"),
                target.get("movie_id"),
                target.get("series_id"),
                target.get("tags"),
                target.get("detection", "broken_symlink"),
                target.get("status", "détecté"),
            ),
        )
        inserted += 1
    await db.commit()

    # Backfill metadata for results that couldn't be matched (EpisodeFiles gone)
    await db.execute(
        "UPDATE results SET"
        " series_id = COALESCE(results.series_id, ("
        "   SELECT series_id FROM results r2"
        "   WHERE r2.symlink_path = results.symlink_path"
        "   AND r2.source = results.source"
        "   AND r2.series_id IS NOT NULL AND r2.id != results.id LIMIT 1"
        " )),"
        " season = COALESCE(results.season, ("
        "   SELECT season FROM results r2"
        "   WHERE r2.symlink_path = results.symlink_path"
        "   AND r2.source = results.source"
        "   AND r2.season IS NOT NULL AND r2.id != results.id LIMIT 1"
        " )),"
        " file_id = COALESCE(results.file_id, ("
        "   SELECT file_id FROM results r2"
        "   WHERE r2.symlink_path = results.symlink_path"
        "   AND r2.source = results.source"
        "   AND r2.file_id IS NOT NULL AND r2.id != results.id LIMIT 1"
        " )),"
        " media_title = CASE WHEN results.media_title IS NULL OR results.media_title = '' THEN ("
        "   SELECT media_title FROM results r2"
        "   WHERE r2.symlink_path = results.symlink_path"
        "   AND r2.source = results.source"
        "   AND r2.media_title IS NOT NULL AND r2.media_title != '' AND r2.id != results.id LIMIT 1"
        " ) ELSE results.media_title END"
        " WHERE scan_id = ?"
        " AND (series_id IS NULL OR season IS NULL"
        "   OR file_id IS NULL OR media_title IS NULL OR media_title = '')",
        (scan_id,),
    )
    await db.commit()

    if inserted == 0:
        await db.execute(
            "UPDATE scans SET summary = 'Aucun nouveau symlink cassé' WHERE id = ?",
            (scan_id,),
        )
        await db.commit()
        logger.info("Scan: no new broken symlinks for %s", source)
        return {
            "ok": True,
            "scan_id": scan_id,
            "source": source,
            "mode": mode,
            "total": result.get("total", 0),
            "broken": result.get("broken", 0),
            "processed": 0,
            "inserted": 0,
            "status": result["status"],
            "cleanup": {"deleted": 0, "failed": 0},
        }

    config = load_config()

    cleanup_stats = {"deleted": 0, "failed": 0}
    if mode == "clean":
        cleanup_stats = await process_all_detected(source, db, scan_id)
        summary_parts = []
        if cleanup_stats.get("deleted"):
            summary_parts.append(f"{cleanup_stats['deleted']} supprimés")
        if cleanup_stats.get("failed"):
            summary_parts.append(f"{cleanup_stats['failed']} échecs")
        summary = ", ".join(summary_parts) if summary_parts else "0 traités"
        await db.execute(
            "UPDATE scans SET processed = ?, summary = ? WHERE id = ?",
            (cleanup_stats.get("deleted", 0), summary, scan_id),
        )
        await db.commit()

    await notify_scan(config, source, result)

    logger.info(
        "Scan completed: source=%s mode=%s total=%d broken=%d inserted=%d cleanup_deleted=%d",
        source,
        mode,
        result.get("total", 0),
        result.get("broken", 0),
        inserted,
        cleanup_stats.get("deleted", 0),
    )
    return {
        "ok": True,
        "scan_id": scan_id,
        "source": source,
        "mode": mode,
        "total": result.get("total", 0),
        "broken": result.get("broken", 0),
        "processed": cleanup_stats.get("deleted", 0) if mode == "clean" else 0,
        "inserted": inserted,
        "status": result["status"],
        "cleanup": cleanup_stats,
    }


@router.get("/api/scan/{source}/status")
async def scan_status(source: str):
    status = await scanner.get_scan_status(source)
    return status


@router.get("/fastscan", response_class=HTMLResponse)
async def fastscan_page():
    return RedirectResponse(url="/scan?mode=fast", status_code=301)


@router.post("/api/fast-scan")
async def trigger_fast_scan(limit: int = 0):
    config = load_config()
    all_results = []
    total_all = broken_all = 0

    for source_name, cfg in [("radarr", config.radarr), ("sonarr", config.sonarr)]:
        if not cfg.library_roots or not cfg.target_prefixes:
            continue
        results, total, matching, broken = filescanner.scan_library_roots(
            cfg.library_roots, cfg.target_prefixes, limit
        )
        for r in results:
            r["source"] = source_name
        all_results.extend(results)
        total_all += total
        broken_all += broken

    logger.info(
        "Fast scan done: total=%d broken=%d",
        total_all,
        broken_all,
    )
    return {
        "ok": True,
        "scanned_at": datetime.now().isoformat(),
        "total": total_all,
        "broken": broken_all,
        "results": all_results,
    }
