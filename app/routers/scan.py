from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services import scanner
from app.templates import templates

router = APIRouter()


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(request: Request):
    return templates.TemplateResponse(request, "scan.html")


@router.post("/api/scan/{source}")
async def trigger_scan(source: str, mode: str = "simulate", db: Connection = Depends(get_db)):
    if source not in ("radarr", "sonarr"):
        return JSONResponse({"error": "source invalide"}, status_code=400)

    result = await scanner.start_scan(source, mode)
    if result["status"] == "error":
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
            " media_type, media_title, season, episode, file_id, tags, detection, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                target.get("tags"),
                target.get("detection", "broken_symlink"),
                target.get("status", "detected"),
            ),
        )
    await db.commit()

    return {
        "ok": True,
        "scan_id": scan_id,
        "source": source,
        "mode": mode,
        "total": result.get("total", 0),
        "broken": result.get("broken", 0),
        "processed": result.get("matching", 0),
        "status": result["status"],
    }


@router.get("/api/scan/{source}/status")
async def scan_status(source: str):
    status = await scanner.get_scan_status(source)
    return status
