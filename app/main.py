from fastapi import FastAPI
from app.database import init_db
from app.routers import web
from pathlib import Path
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="SymlinkRepair", lifespan=lifespan)
app.include_router(web.router)
