import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.database import init_db
from app.error_handlers import general_error_handler, not_found_handler
from app.logging_config import setup_logging
from app.routers import admin, api_config, config_ui, health, orphans, reports, results, scan, web
from app.services.orphan_scheduler import start as start_orphan_scheduler
from app.services.orphan_scheduler import stop as stop_orphan_scheduler
from app.services.rechecker import start as start_rechecker
from app.services.rechecker import stop as stop_rechecker
from app.services.retryer import start as start_retryer
from app.services.retryer import stop as stop_retryer
from app.services.scheduler import start as start_scheduler
from app.services.scheduler import stop as stop_scheduler
from app.services.verifier import start as start_verifier
from app.services.verifier import stop as stop_verifier

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SymlinkRepair starting")
    await init_db()
    start_scheduler()
    start_verifier()
    start_retryer()
    start_rechecker()
    start_orphan_scheduler()
    logger.info("SymlinkRepair started")
    yield
    logger.info("SymlinkRepair shutting down")
    stop_orphan_scheduler()
    stop_rechecker()
    stop_retryer()
    stop_verifier()
    stop_scheduler()


app = FastAPI(title="SymlinkRepair", lifespan=lifespan)


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "text/html" in ct:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif "/static/" in str(request.url.path):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    return response


app.include_router(admin.router)
app.include_router(web.router)
app.include_router(health.router)
app.include_router(config_ui.router)
app.include_router(api_config.router)
app.include_router(scan.router)
app.include_router(results.router)
app.include_router(reports.router)
app.include_router(orphans.router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.add_exception_handler(StarletteHTTPException, not_found_handler)
app.add_exception_handler(Exception, general_error_handler)
