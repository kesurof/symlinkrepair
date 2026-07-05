from pathlib import Path

import jinja2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
    cache_size=0,
    auto_reload=True,
)
templates = Jinja2Templates(env=jinja_env)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")
