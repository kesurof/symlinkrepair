from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.database import get_db
from app.services.cleanup import process_result, process_result_season
from app.services.config_service import load_config
from app.services.discord import notify_cleanup
from app.templates import templates

router = APIRouter()


@router.get("/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    db: Connection = Depends(get_db),
    source: str = "",
    status: str = "",
    season: str = "",
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

    if source:
        where += " AND source = ?"
        params.append(source)
    if status:
        where += " AND status = ?"
        params.append(status)
    if season:
        where += " AND season = ?"
        params.append(int(season))
    if q:
        where += " AND (media_title LIKE ? OR symlink_path LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    count_cursor = await db.execute(f"SELECT COUNT(*) FROM results {where}", params)
    total = (await count_cursor.fetchone())[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    cursor = await db.execute(
        f"SELECT id, source, media_title, media_type, season,"
        f" symlink_path, status, action FROM results {where}"
        f" ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )
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
            "active_season": season,
            "active_q": q,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
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
async def process_single_result(
    result_id: int, delete_season: bool = False, db: Connection = Depends(get_db)
):
    cursor = await db.execute("SELECT * FROM results WHERE id = ?", (result_id,))
    row = await cursor.fetchone()
    if not row:
        return JSONResponse({"ok": False, "error": "Résultat introuvable"}, status_code=404)

    result = dict(row)

    if delete_season and result.get("source") == "sonarr":
        outcome = await process_result_season(result, db)
    else:
        outcome = await process_result(result)

        if outcome["ok"]:
            await db.execute(
                "UPDATE results SET status = 'processed', action = 'api_delete',"
                " action_date = datetime('now') WHERE id = ?",
                (result_id,),
            )
            await db.commit()

    config = load_config()
    await notify_cleanup(config, result, outcome.get("actions", {}))

    return outcome


@router.post("/api/results/batch")
async def batch_action(request: Request, db: Connection = Depends(get_db)):
    body = await request.json()
    action = body.get("action", "")
    ids = body.get("ids", [])

    if not ids:
        return JSONResponse({"ok": False, "error": "Aucun ID fourni"}, status_code=400)

    if action == "ignore":
        await db.execute(
            f"UPDATE results SET status = 'ignored', action = 'ignored',"
            f" action_date = datetime('now') WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
    elif action == "fix":
        await db.execute(
            f"UPDATE results SET status = 'fixed', action = 'manual_fix',"
            f" action_date = datetime('now') WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
    elif action == "recheck":
        await db.execute(
            f"UPDATE results SET status = 'recheck_needed',"
            f" action = NULL, action_date = NULL WHERE id IN ({','.join('?' for _ in ids)})",
            ids,
        )
    else:
        return JSONResponse({"ok": False, "error": f"Action inconnue: {action}"}, status_code=400)

    await db.commit()
    return {"ok": True, "affected": len(ids)}
