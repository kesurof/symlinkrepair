import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.error_handlers import general_error_handler, not_found_handler
from app.logging_config import setup_logging
from app.routers import api_config, config_ui, health, reports, results, scan, web
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
    logger.info("SymlinkRepair started")
    yield
    logger.info("SymlinkRepair shutting down")
    stop_retryer()
    stop_verifier()
    stop_scheduler()


app = FastAPI(title="SymlinkRepair", lifespan=lifespan)
app.include_router(web.router)
app.include_router(health.router)
app.include_router(config_ui.router)
app.include_router(api_config.router)
app.include_router(scan.router)
app.include_router(results.router)
app.include_router(reports.router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.add_exception_handler(StarletteHTTPException, not_found_handler)
app.add_exception_handler(Exception, general_error_handler)
