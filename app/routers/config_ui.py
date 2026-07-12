from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templates import templates

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "radarr_naming_guide": "/static/config_arr/radarr.png",
            "sonarr_naming_guide": "/static/config_arr/sonarr.png",
        },
    )
