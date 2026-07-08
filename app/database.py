import logging
from pathlib import Path

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

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
                status          TEXT NOT NULL DEFAULT 'détecté',
                action          TEXT,
                action_date     TEXT,
                notes           TEXT,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            );

            CREATE INDEX IF NOT EXISTS idx_results_scan ON results(scan_id);
            CREATE INDEX IF NOT EXISTS idx_results_status ON results(status);
            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);
        """)

        for col in ("movie_id", "series_id", "search_count", "created_at"):
            try:
                coltype = "INTEGER DEFAULT 0" if col != "created_at" else "TEXT"
                await db.execute(f"ALTER TABLE results ADD COLUMN {col} {coltype}")
            except Exception:
                pass

        await db.execute(
            "UPDATE results SET created_at = ("
            "  SELECT created_at FROM scans WHERE scans.id = results.scan_id"
            ") WHERE created_at IS NULL"
        )

        for old, new in [
            ("detected", "détecté"),
            ("ignored", "ignoré"),
            ("fixed", "remplacé"),
            ("processed", "surveillance"),
            ("en_attente", "surveillance"),
            ("not_replaced", "non_remplacé"),
            ("failed", "échoué"),
            ("recherche", "surveillance"),
        ]:
            await db.execute(
                "UPDATE results SET status = ? WHERE status = ?",
                (new, old),
            )

        await db.execute("UPDATE results SET status = 'remplacé' WHERE status = 'réparé'")

        cursor = await db.execute(
            "UPDATE results SET status = 'ignoré', action = 'cleaned_duplicate',"
            " action_date = datetime('now')"
            " WHERE status = 'détecté' AND (symlink_path, source) IN ("
            "   SELECT symlink_path, source FROM results"
            "   WHERE status = 'remplacé'"
            " )"
        )
        if cursor.rowcount:
            logger.info("Cleaned up %d historical duplicate results", cursor.rowcount)

        await db.commit()
    logger.info("Database initialized at %s", DATABASE_PATH)
