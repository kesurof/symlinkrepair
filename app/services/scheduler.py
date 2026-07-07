import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite

from app.database import DATABASE_PATH
from app.services import scanner
from app.services.cleanup import process_all_detected
from app.services.config_service import load_config
from app.services.discord import notify_cleanup, notify_scan, notify_season_cleanup

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _dedup_or_insert(db, scan_id, target, source):
    existing = await db.execute(
        "SELECT id FROM results WHERE symlink_path = ? AND source = ?"
        " AND status IN ('détecté', 'en_attente', 'recherche') LIMIT 1",
        (target.get("symlink_path", ""), target.get("source", source)),
    )
    if await existing.fetchone():
        return False
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
            target.get("status", "détecté"),
        ),
    )
    return True


async def _trigger_scan(source: str):
    try:
        result = await scanner.start_scan(source, "clean", 0)
        if result["status"] == "error":
            logger.warning("%s scan error: %s", source, result.get("error"))
            return

        db = await aiosqlite.connect(str(DATABASE_PATH))
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "INSERT INTO scans"
                " (source, mode, status, total, broken, processed, summary, completed_at)"
                " VALUES (?, ?, ?, ?, ?, 0, ?, datetime('now'))",
                (
                    source,
                    "clean",
                    result["status"],
                    result.get("total", 0),
                    result.get("broken", 0),
                    "",
                ),
            )
            scan_id = cursor.lastrowid

            inserted = 0
            for target in result.get("targets", []):
                if await _dedup_or_insert(db, scan_id, target, source):
                    inserted += 1
            await db.commit()

            if inserted == 0:
                await db.execute(
                    "UPDATE scans SET summary = 'Aucun nouveau symlink cassé' WHERE id = ?",
                    (scan_id,),
                )
                await db.commit()
                logger.info("%s scan: no new broken symlinks", source)
                return

            cleanup_stats = await process_all_detected(source, db, scan_id)

            summary_parts = []
            if cleanup_stats.get("deleted"):
                summary_parts.append(f"{cleanup_stats['deleted']} supprimés")
            if cleanup_stats.get("failed"):
                summary_parts.append(f"{cleanup_stats['failed']} échecs")
            summary = ", ".join(summary_parts) if summary_parts else "0 traités"
            await db.execute(
                "UPDATE scans SET processed = ?, summary = ? WHERE id = ?",
                (cleanup_stats.get("deleted", 0), summary, scan_id),
            )
            await db.commit()

            config = load_config()
            await notify_scan(config, source, result)
            if cleanup_stats.get("deleted"):
                if source == "sonarr":
                    sonarr_seasons = {}
                    for target in result.get("targets", []):
                        if target.get("series_id") and target.get("season") is not None:
                            key = (target["series_id"], target["season"])
                            if key not in sonarr_seasons:
                                sonarr_seasons[key] = {
                                    "title": target.get("media_title", ""),
                                    "processed": 0,
                                    "total": 0,
                                }
                            sonarr_seasons[key]["total"] += 1
                            sonarr_seasons[key]["processed"] += 1
                    for (sid, snum), info in sonarr_seasons.items():
                        await notify_season_cleanup(
                            config,
                            series_title=info["title"],
                            season=snum,
                            source="sonarr",
                            outcome={"processed": info["processed"], "total": info["total"]},
                        )
                else:
                    for target in result.get("targets", []):
                        title = target.get("media_title") or ""
                        if title:
                            action_log = {
                                "api_delete": True,
                                "symlink_removed": True,
                                "refresh": config.defaults.rescan,
                                "search": config.defaults.search,
                            }
                            fake_result = {"source": source, "media_title": title}
                            await notify_cleanup(config, fake_result, action_log)

            logger.info(
                "%s scan done: %d broken, %d new, %d deleted, %d failed",
                source,
                result.get("broken", 0),
                inserted,
                cleanup_stats.get("deleted", 0),
                cleanup_stats.get("failed", 0),
            )
        finally:
            await db.close()
    except Exception as e:
        logger.error("%s scan failed: %s", source, e)


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
        logger.warning("Failed to check last scan for %s: %s", source, e)
        return False


async def _scheduler_loop():
    logger.info("Background loop started")
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
                    logger.info("Triggering %s scan (interval=%dh)", source, interval)
                    await _trigger_scan(source)
        except Exception as e:
            logger.error("Loop error: %s", e)

        await asyncio.sleep(60)


def start():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Scheduler started")


def stop():
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Scheduler stopped")
