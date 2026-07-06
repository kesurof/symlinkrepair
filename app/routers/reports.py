import logging
from datetime import datetime, timedelta

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

    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

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
            "today": today_str,
            "yesterday": yesterday_str,
        },
    )


@router.get("/api/stats")
async def stats(db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT"
        " (SELECT COUNT(*) FROM scans) AS total_scans,"
        " (SELECT COUNT(*) FROM results) AS total_results,"
        " (SELECT COUNT(*) FROM results WHERE status IN ('détecté','recherche')) AS broken,"
        " (SELECT COALESCE(SUM(CASE WHEN status IN ('remplacé','en_attente','ignoré')"
        "  THEN 1 ELSE 0 END), 0) FROM results) AS fixed"
    )
    row = dict(await cursor.fetchone())

    cursor2 = await db.execute(
        "SELECT id, source, mode, status, total, broken, processed, created_at"
        " FROM scans ORDER BY id DESC LIMIT 1"
    )
    last = await cursor2.fetchone()
    row["last_scan"] = dict(last) if last else None

    cursor3 = await db.execute("""
        SELECT
         (SELECT COUNT(*) FROM results
          WHERE source='radarr' AND status IN ('détecté','recherche')) AS br,
         (SELECT COUNT(*) FROM results
          WHERE source='sonarr' AND status IN ('détecté','recherche')) AS bs,
         (SELECT COUNT(*) FROM results WHERE source='radarr') AS tr,
         (SELECT COUNT(*) FROM results WHERE source='sonarr') AS ts,
         (SELECT COUNT(*) FROM scans WHERE DATE(created_at)=DATE('now')) AS st
    """)
    extra = dict(await cursor3.fetchone())
    row["broken_radarr"] = extra["br"]
    row["broken_sonarr"] = extra["bs"]
    row["total_radarr"] = extra["tr"]
    row["total_sonarr"] = extra["ts"]
    row["scans_today"] = extra["st"]
    return row


@router.get("/api/stats/history")
async def stats_history(db: Connection = Depends(get_db), days: int = 30):
    cursor = await db.execute(
        "SELECT DATE(s.created_at) as day, COUNT(*) as detected"
        " FROM results r JOIN scans s ON r.scan_id = s.id"
        " WHERE s.created_at >= DATE('now', ? || ' days')"
        " GROUP BY DATE(s.created_at) ORDER BY day",
        (f"-{days}",),
    )
    detected_by_day = {r[0]: r[1] for r in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT DATE(action_date) as day,"
        "  SUM(CASE WHEN status = 'remplacé' THEN 1 ELSE 0 END) as replaced"
        " FROM results"
        " WHERE action_date IS NOT NULL AND status = 'remplacé'"
        "  AND action_date >= DATE('now', ? || ' days')"
        " GROUP BY DATE(action_date) ORDER BY day",
        (f"-{days}",),
    )
    action_by_day = {r[0]: {"replaced": r[1]} for r in await cursor.fetchall()}

    today = datetime.now().date()
    days_list = []
    detected_series = []
    replaced_series = []
    cumulative_list = []
    running = 0

    for i in range(days - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        d = detected_by_day.get(day, 0)
        p = action_by_day.get(day, {}).get("replaced", 0)
        running += d - p
        days_list.append(day)
        detected_series.append(d)
        replaced_series.append(p)
        cumulative_list.append(max(0, running))

    return {
        "days": days_list,
        "series": {
            "detected": detected_series,
            "replaced": replaced_series,
            "cumulative": cumulative_list,
        },
    }


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
