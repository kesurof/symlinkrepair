import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite

from app.database import DATABASE_PATH
from app.services import scanner
from app.services.config_service import load_config

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _trigger_scan(source: str):
    logger.info("Scheduler: triggering %s scan", source)
    try:
        result = await scanner.start_scan(source, "simulate", 0)
        if result["status"] == "error":
            logger.warning("Scheduler: %s scan error: %s", source, result.get("error"))
            return

        db = await aiosqlite.connect(str(DATABASE_PATH))
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "INSERT INTO scans"
                " (source, mode, status, total, broken, processed, summary, completed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    source,
                    "simulate",
                    result["status"],
                    result.get("total", 0),
                    result.get("broken", 0),
                    result.get("matching", 0),
                    "",
                ),
            )
            scan_id = cursor.lastrowid

            for target in result.get("targets", []):
                await db.execute(
                    "INSERT INTO results (scan_id, source, symlink_path, target_path,"
                    " media_type, media_title, season, episode, file_id, movie_id, series_id,"
                    " tags, detection, status)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        scan_id,
                        target.get("source", source),
                        target.get("symlink_path", ""),
                        target.get("target_path", ""),
                        target.get("media_type"),
                        target.get("media_title"),
                        target.get("season"),
                        target.get("episode"),
                        target.get("file_id"),
                        target.get("movie_id"),
                        target.get("series_id"),
                        target.get("tags"),
                        target.get("detection", "broken_symlink"),
                        target.get("status", "detected"),
                    ),
                )
            await db.commit()
            logger.info(
                "Scheduler: %s scan done, %s results", source, len(result.get("targets", []))
            )
        finally:
            await db.close()
    except Exception as e:
        logger.error("Scheduler: %s scan failed: %s", source, e)


async def _should_run(source: str, interval_hours: int) -> bool:
    try:
        db = await aiosqlite.connect(str(DATABASE_PATH))
        try:
            cursor = await db.execute(
                "SELECT completed_at FROM scans WHERE source = ?"
                " AND completed_at IS NOT NULL ORDER BY id DESC LIMIT 1",
                (source,),
            )
            row = await cursor.fetchone()
            if row is None:
                return True
            last = datetime.fromisoformat(row[0])
            return datetime.now() - last > timedelta(hours=interval_hours)
        finally:
            await db.close()
    except Exception as e:
        logger.warning("Scheduler: failed to check last scan for %s: %s", source, e)
        return False


async def _scheduler_loop():
    logger.info("Scheduler: starting background loop")
    while True:
        try:
            config = load_config()
            sched = config.scheduler

            for source, enabled_key, interval_key in [
                ("radarr", "radarr_enabled", "radarr_interval_hours"),
                ("sonarr", "sonarr_enabled", "sonarr_interval_hours"),
            ]:
                if not getattr(sched, enabled_key):
                    continue
                interval = getattr(sched, interval_key)
                if interval < 1:
                    interval = 1
                if await _should_run(source, interval):
                    await _trigger_scan(source)
        except Exception as e:
            logger.error("Scheduler: loop error: %s", e)

        await asyncio.sleep(60)


def start():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Scheduler: started")


def stop():
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Scheduler: stopped")
