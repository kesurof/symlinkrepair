from pathlib import Path

import jinja2
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).resolve().parent / "templates"),
    cache_size=0,
    auto_reload=True,
)
templates = Jinja2Templates(env=jinja_env)


async def not_found_handler(request: Request, exc):
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "404.html", status_code=404)
    return JSONResponse({"detail": "Not found"}, status_code=404)


async def general_error_handler(request: Request, exc):
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"detail": str(exc)},
            status_code=500,
        )
    return JSONResponse({"detail": str(exc)}, status_code=500)
