from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import init_db
from app.error_handlers import general_error_handler, not_found_handler
from app.logging_config import setup_logging
from app.routers import health, web

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="SymlinkRepair", lifespan=lifespan)
app.include_router(web.router)
app.include_router(health.router)

app.add_exception_handler(StarletteHTTPException, not_found_handler)
app.add_exception_handler(Exception, general_error_handler)
