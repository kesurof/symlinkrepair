from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.cleanup import process_result
from app.templates import templates

router = APIRouter()


@router.get("/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    db: Connection = Depends(get_db),
    source: str = "",
    status: str = "",
    q: str = "",
):
    query = (
        "SELECT id, source, media_title, media_type, season,"
        " symlink_path, status, action FROM results WHERE 1=1"
    )
    params = []

    if source:
        query += " AND source = ?"
        params.append(source)
    if status:
        query += " AND status = ?"
        params.append(status)
    if q:
        query += " AND (media_title LIKE ? OR symlink_path LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    query += " ORDER BY id DESC LIMIT 100"
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    items = [dict(r) for r in rows]

    cursor_src = await db.execute("SELECT DISTINCT source FROM results")
    sources = [r[0] for r in await cursor_src.fetchall()]
    cursor_st = await db.execute("SELECT DISTINCT status FROM results")
    statuses = [r[0] for r in await cursor_st.fetchall()]

    return templates.TemplateResponse(
        request,
        "results.html",
        {
            "items": items,
            "sources": sources,
            "statuses": statuses,
            "active_source": source,
            "active_status": status,
            "active_q": q,
        },
    )


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
        "UPDATE results SET status = 'ignored', action = 'ignored',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    return {"ok": True}


@router.post("/api/results/{result_id}/recheck")
async def recheck_result(result_id: int, db: Connection = Depends(get_db)):
    await db.execute(
        "UPDATE results SET status = 'recheck_needed',"
        " action = NULL, action_date = NULL WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    return {"ok": True}


@router.post("/api/results/{result_id}/fix")
async def fix_result(result_id: int, db: Connection = Depends(get_db)):
    await db.execute(
        "UPDATE results SET status = 'fixed', action = 'manual_fix',"
        " action_date = datetime('now') WHERE id = ?",
        (result_id,),
    )
    await db.commit()
    return {"ok": True}


@router.post("/api/results/{result_id}/process")
async def process_single_result(result_id: int, db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)

    result = dict(row)
    outcome = await process_result(result)

    if outcome["ok"]:
        await db.execute(
            "UPDATE results SET status = 'processed', action = 'api_delete',"
            " action_date = datetime('now') WHERE id = ?",
            (result_id,),
        )
        await db.commit()

    return outcome
