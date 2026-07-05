from pathlib import Path

import aiosqlite

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
    async with aiosqlite.connect(str(DATABASE_PATH), timeout=30) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS scans (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                mode        TEXT NOT NULL DEFAULT 'simulate',
                status      TEXT NOT NULL DEFAULT 'running',
                total       INTEGER DEFAULT 0,
                broken      INTEGER DEFAULT 0,
                processed   INTEGER DEFAULT 0,
                summary     TEXT,
                report_file TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS results (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id         INTEGER NOT NULL,
                source          TEXT NOT NULL,
                symlink_path    TEXT NOT NULL,
                target_path     TEXT,
                media_type      TEXT,
                media_title     TEXT,
                season          INTEGER,
                episode         INTEGER,
                file_id         INTEGER,
                movie_id        INTEGER,
                series_id       INTEGER,
                tags            TEXT,
                detection       TEXT NOT NULL DEFAULT 'broken_symlink',
                status          TEXT NOT NULL DEFAULT 'detected',
                action          TEXT,
                action_date     TEXT,
                notes           TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            );

            CREATE INDEX IF NOT EXISTS idx_results_scan ON results(scan_id);
            CREATE INDEX IF NOT EXISTS idx_results_status ON results(status);
            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);
        """)

        for col in ("movie_id", "series_id"):
            try:
                await db.execute(f"ALTER TABLE results ADD COLUMN {col} INTEGER")
            except Exception:
                pass

        await db.commit()
