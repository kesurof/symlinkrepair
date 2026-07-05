import aiosqlite
from pathlib import Path
from app.config import settings

DATABASE_PATH = Path(settings.data_dir) / "symlinkrepair.db"


async def get_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DATABASE_PATH)) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                broken_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                symlink_path TEXT NOT NULL,
                target_path TEXT,
                status TEXT NOT NULL DEFAULT 'broken',
                action TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            );
        """)
        await db.commit()
