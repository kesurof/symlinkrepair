import logging
from datetime import datetime

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services import filescanner, scanner
from app.services.cleanup import process_all_detected
from app.services.config_service import load_config
from app.services.discord import notify_scan
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    config = load_config()
    return templates.TemplateResponse(
        request, "scan.html", {"default_limit": config.defaults.limit}
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
        " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            source,
            mode,
            result["status"],
            result.get("total", 0),
            result.get("broken", 0),
            result.get("matching", 0),
            "",
        ),
    )
    scan_id = cursor.lastrowid

    # Store results
    for target in result.get("targets", []):
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
    await db.commit()

    config = load_config()

    cleanup_stats = {"deleted": 0, "failed": 0}
    if mode == "clean":
        cleanup_stats = await process_all_detected(source, db, scan_id)

    await notify_scan(config, source, result)

    logger.info(
        "Scan completed: source=%s mode=%s total=%d broken=%d processed=%d cleanup_deleted=%d",
        source,
        mode,
        result.get("total", 0),
        result.get("broken", 0),
        result.get("matching", 0),
        cleanup_stats.get("deleted", 0),
    )
    return {
        "ok": True,
        "scan_id": scan_id,
        "source": source,
        "mode": mode,
        "total": result.get("total", 0),
        "broken": result.get("broken", 0),
        "processed": result.get("matching", 0),
        "status": result["status"],
        "cleanup": cleanup_stats,
    }


@router.get("/api/scan/{source}/status")
async def scan_status(source: str):
    status = await scanner.get_scan_status(source)
    return status


@router.get("/fastscan", response_class=HTMLResponse)
async def fastscan_page(request: Request):
    return templates.TemplateResponse(request, "fastscan.html")


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
