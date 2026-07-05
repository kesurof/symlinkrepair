from fastapi import Request
from fastapi.responses import JSONResponse

from app.templates import templates


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
