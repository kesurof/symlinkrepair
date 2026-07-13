import logging

from aiosqlite import Connection
from fastapi import APIRouter, Depends

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/reset-data")
async def reset_data(db: Connection = Depends(get_db)):
    logger.warning("Resetting all scan data...")
    await db.execute("DELETE FROM results")
    await db.execute("DELETE FROM orphan_magnets")
    await db.execute("DELETE FROM scans")
    await db.commit()
    logger.warning("All scan data has been wiped (config preserved)")
    return {"ok": True}
