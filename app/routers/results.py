from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.database import get_db
from app.templates import templates

router = APIRouter()


@router.get("/results", response_class=HTMLResponse)
async def results_page(request: Request, db: Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, source, media_title, media_type, season, symlink_path, status, action "
        "FROM results ORDER BY id DESC LIMIT 100"
    )
    rows = await cursor.fetchall()
    items = [dict(r) for r in rows]
    return templates.TemplateResponse(request, "results.html", {"items": items})


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
