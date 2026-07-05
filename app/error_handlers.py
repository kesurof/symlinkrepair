import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.templates import templates

logger = logging.getLogger(__name__)


async def not_found_handler(request: Request, exc):
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(request, "404.html", status_code=404)
    return JSONResponse({"detail": "Not found"}, status_code=404)


async def general_error_handler(request: Request, exc):
    logger.exception("Unhandled error: %s", exc)
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse(
            request,
            "error.html",
            {"detail": "Une erreur interne est survenue"},
            status_code=500,
        )
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
