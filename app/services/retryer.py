import asyncio
import logging
from datetime import datetime, timezone

import aiosqlite

from app.database import DATABASE_PATH
from app.services.config_service import load_config
from app.services.radarr import search_movies
from app.services.sonarr import search_season

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_interval: float = 3600
_max_daily: int = 3
_enabled: bool = False


async def _search_one(row: dict) -> bool:
    config = load_config()
    source = row.get("source", "")
    if source == "radarr":
        movie_id = row.get("movie_id")
        if not movie_id or not config.radarr.api_key:
            return False
        return await search_movies(config.radarr.url, config.radarr.api_key, [movie_id])
    elif source == "sonarr":
        series_id = row.get("series_id")
        season = row.get("season")
        if not series_id or season is None or not config.sonarr.api_key:
            return False
        return await search_season(config.sonarr.url, config.sonarr.api_key, series_id, season)
    return False


async def _retryer_loop():
    logger.info("Retryer loop started (interval=%.0fs, max_daily=%d)", _interval, _max_daily)
    while True:
        try:
            reload_config()
            if not _enabled:
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(_interval)

            try:
                db = await aiosqlite.connect(str(DATABASE_PATH))
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT id, source, media_title, movie_id, series_id, season,"
                    " search_count, action_date"
                    " FROM results WHERE status = 'non_remplacé'"
                    " ORDER BY action_date ASC"
                )
                rows = [dict(r) for r in await cursor.fetchall()]
                await db.close()
            except Exception as e:
                logger.warning("Retryer DB query failed: %s", e)
                continue

            if not rows:
                logger.info("Retryer: no non_remplacé items found")
                continue

            logger.info("Retryer: checking %d non_remplacé items...", len(rows))
            now = datetime.now(timezone.utc).isoformat()
            attempted = 0

            for row in rows:
                try:
                    action_date = row.get("action_date")
                    if action_date and action_date + "Z" > now:
                        continue

                    search_count = row.get("search_count") or 0
                    if search_count >= _max_daily:
                        continue

                    ok = await _search_one(row)
                    if ok:
                        attempted += 1
                        try:
                            db2 = await aiosqlite.connect(str(DATABASE_PATH))
                            await db2.execute(
                                "UPDATE results SET search_count = search_count + 1,"
                                " action_date = datetime('now') WHERE id = ?",
                                (row["id"],),
                            )
                            await db2.commit()
                            await db2.close()
                        except Exception as e:
                            logger.warning("Retryer DB update failed for id=%d: %s", row["id"], e)

                    title = row.get("media_title") or "?"
                    src = row.get("source", "")
                    logger.info(
                        "Retryer: %s search for %s (id=%d) — %s",
                        "triggered" if ok else "skipped",
                        title,
                        row["id"],
                        src if ok else "api_unavailable",
                    )
                except Exception as e:
                    logger.warning("Retryer error for id=%d: %s", row.get("id"), e)

            if attempted:
                logger.info("Retryer: %d searches triggered", attempted)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Retryer loop crashed: %s — restarting", e)
            await asyncio.sleep(10)


def reload_config():
    global _interval, _max_daily, _enabled
    config = load_config()
    r = config.retryer
    _enabled = r.enabled
    _interval = float(r.interval_minutes * 60)
    _max_daily = r.max_daily_retries


def start():
    global _task
    reload_config()
    if _task is None or _task.done():
        _task = asyncio.create_task(_retryer_loop())
        logger.info("Retryer started (interval=%.0fs, max_daily=%d)", _interval, _max_daily)


def stop():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        logger.info("Retryer stopped")
