from fastapi import APIRouter

from app.database import DATABASE_PATH

router = APIRouter()


@router.get("/health")
async def health():
    db_ok = DATABASE_PATH.exists()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "not initialized",
    }
