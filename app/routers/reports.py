from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.database import get_db
from app.templates import templates

router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, source, mode, status, total, broken, processed, created_at, completed_at "
        "FROM scans ORDER BY id DESC LIMIT 50"
    )
    rows = await cursor.fetchall()
    scans = [dict(r) for r in rows]
    return templates.TemplateResponse(request, "reports.html", {"scans": scans})


@router.get("/api/stats")
async def stats(db: Connection = Depends(get_db)):
    total_scans = await db.execute("SELECT COUNT(*) FROM scans")
    total_results = await db.execute("SELECT COUNT(*) FROM results")
    broken_count = await db.execute("SELECT COUNT(*) FROM results WHERE status = 'detected'")
    fixed_count = await db.execute(
        "SELECT COUNT(*) FROM results WHERE action IN ('fixed', 'processed')"
    )

    return {
        "total_scans": (await total_scans.fetchone())[0],
        "total_results": (await total_results.fetchone())[0],
        "broken": (await broken_count.fetchone())[0],
        "fixed": (await fixed_count.fetchone())[0],
    }
