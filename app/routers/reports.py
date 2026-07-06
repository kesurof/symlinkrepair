import logging

from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.templates import templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request,
    db: Connection = Depends(get_db),
    source: str = "",
    status: str = "",
    mode: str = "",
    q: str = "",
    page: int = 1,
    per_page: int = 25,
):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 25

    where = "WHERE 1=1"
    params = []

    if source:
        where += " AND source = ?"
        params.append(source)
    if status:
        where += " AND status = ?"
        params.append(status)
    if mode:
        where += " AND mode = ?"
        params.append(mode)
    if q:
        where += " AND (source LIKE ? OR mode LIKE ? OR status LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])

    count_cursor = await db.execute(f"SELECT COUNT(*) FROM scans {where}", params)
    total = (await count_cursor.fetchone())[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    cursor = await db.execute(
        f"SELECT id, source, mode, status, total, broken, processed, created_at, completed_at"
        f" FROM scans {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )
    rows = await cursor.fetchall()
    scans = [dict(r) for r in rows]

    cursor_src = await db.execute("SELECT DISTINCT source FROM scans")
    sources = [r[0] for r in await cursor_src.fetchall()]
    cursor_st = await db.execute("SELECT DISTINCT status FROM scans")
    statuses = [r[0] for r in await cursor_st.fetchall()]
    cursor_md = await db.execute("SELECT DISTINCT mode FROM scans")
    modes = [r[0] for r in await cursor_md.fetchall()]

    is_htmx = request.headers.get("hx-request") == "true"
    template = "partials/reports_content.html" if is_htmx else "reports.html"

    return templates.TemplateResponse(
        request,
        template,
        {
            "scans": scans,
            "sources": sources,
            "statuses": statuses,
            "modes": modes,
            "active_source": source,
            "active_status": status,
            "active_mode": mode,
            "active_q": q,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/api/stats")
async def stats(db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT"
        " (SELECT COUNT(*) FROM scans) AS total_scans,"
        " (SELECT COUNT(*) FROM results) AS total_results,"
        " (SELECT COUNT(*) FROM results WHERE status IN ('détecté','recherche')) AS broken,"
        " (SELECT COALESCE(SUM(CASE WHEN status IN ('réparé','remplacé','en_attente','ignoré')"
        "  THEN 1 ELSE 0 END), 0) FROM results) AS fixed"
    )
    row = await cursor.fetchone()
    return dict(row)


@router.post("/api/scans/delete")
async def delete_scans(request: Request, db: Connection = Depends(get_db)):
    body = await request.json()
    ids = body.get("ids", [])
    if not ids:
        return JSONResponse({"ok": False, "error": "Aucun ID fourni"}, status_code=400)

    placeholders = ",".join("?" for _ in ids)
    await db.execute(f"DELETE FROM results WHERE scan_id IN ({placeholders})", ids)
    await db.execute(f"DELETE FROM scans WHERE id IN ({placeholders})", ids)
    await db.commit()
    logger.info("Scans deleted: ids=%s count=%d", ids, len(ids))
    return {"ok": True, "affected": len(ids)}
