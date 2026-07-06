import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.database import DATABASE_PATH
from app.services.config_service import load_config
from app.services.radarr import search_movies
from app.services.sonarr import search_season

logger = logging.getLogger(__name__)

_pending: dict[str, dict] = {}
_task: asyncio.Task | None = None
_interval: float = 180
_max_duration: float = 3600
_enabled: bool = True
_heartbeat_count: int = 0


def add(
    symlink_path: str,
    source: str,
    file_id: int,
    media_title: str = "",
    series_id: int | None = None,
    movie_id: int | None = None,
    season: int | None = None,
):
    if not _enabled:
        return
    if not symlink_path:
        return
    now = datetime.now(timezone.utc)
    _pending[symlink_path] = {
        "source": source,
        "file_id": file_id,
        "media_title": media_title or Path(symlink_path).name,
        "series_id": series_id,
        "movie_id": movie_id,
        "season": season,
        "added_at": now,
        "cycle_start": now,
        "search_done": False,
    }
    logger.info(
        "Verifier scheduled: %s (%s) check every %.0fs for %.0fs",
        symlink_path,
        media_title or "?",
        _interval,
        _max_duration,
    )


def pending_count() -> int:
    return len(_pending)


def get_status(symlink_path: str) -> dict | None:
    meta = _pending.get(symlink_path)
    if not meta:
        return None
    now = datetime.now(timezone.utc)
    elapsed = (now - meta["cycle_start"]).total_seconds()
    return {
        "pending": True,
        "added_at": meta["added_at"].isoformat(),
        "cycle_start": meta["cycle_start"].isoformat(),
        "search_done": meta["search_done"],
        "elapsed_seconds": int(elapsed),
        "remaining_seconds": max(0, int(_max_duration - elapsed)),
        "interval_seconds": int(_interval),
        "max_duration_seconds": int(_max_duration),
    }


def remove(symlink_path: str) -> bool:
    if symlink_path in _pending:
        _pending.pop(symlink_path)
        logger.info("Verifier removed: %s", symlink_path)
        return True
    return False


def _check_exists(symlink_path: str) -> bool:
    try:
        if os.path.islink(symlink_path):
            target = os.readlink(symlink_path)
            if os.path.isabs(target):
                target_resolved = target
            else:
                target_resolved = os.path.join(os.path.dirname(symlink_path), target)
            return os.path.exists(os.path.normpath(target_resolved))
        return os.path.exists(symlink_path)
    except OSError:
        return False


async def _update_db_status(symlink_path: str, status: str, action: str):
    try:
        db = await aiosqlite.connect(str(DATABASE_PATH))
        await db.execute(
            "UPDATE results SET status = ?, action = ?, action_date = datetime('now')"
            " WHERE symlink_path = ? AND status = 'en_attente'",
            (status, action, symlink_path),
        )
        await db.commit()
        await db.close()
    except Exception as e:
        logger.warning("Failed to update DB for %s: %s", symlink_path, e)


async def _trigger_search(meta: dict) -> bool:
    config = load_config()
    source = meta["source"]
    if source == "radarr":
        movie_id = meta.get("movie_id")
        if not movie_id or not config.radarr.api_key:
            return False
        logger.info("Verifier forcing search for movie %d", movie_id)
        return await search_movies(config.radarr.url, config.radarr.api_key, [movie_id])
    elif source == "sonarr":
        series_id = meta.get("series_id")
        season = meta.get("season")
        if not series_id or season is None or not config.sonarr.api_key:
            return False
        logger.info("Verifier forcing search for series %d season %d", series_id, season)
        return await search_season(config.sonarr.url, config.sonarr.api_key, series_id, season)
    return False


async def _check_loop():
    global _heartbeat_count
    logger.info(
        "Verifier loop started (interval=%.0fs, max_duration=%.0fs)",
        _interval,
        _max_duration,
    )
    while True:
        try:
            reload_config()
            if not _enabled:
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(_interval)

            if not _pending:
                _heartbeat_count += 1
                if _heartbeat_count % 2 == 0:
                    logger.info("Verifier: waiting for symlinks to verify...")
                continue

            _heartbeat_count = 0
            logger.info("Verifier: checking %d pending symlinks...", len(_pending))
            now = datetime.now(timezone.utc)
            for path, meta in list(_pending.items()):
                try:
                    exists = _check_exists(path)
                    elapsed = (now - meta["cycle_start"]).total_seconds()

                    if exists:
                        logger.info(
                            "Replaced: %s (%s)",
                            path,
                            meta.get("media_title", "?"),
                        )
                        await _update_db_status(path, "remplacé", "verifier_ok")
                        _pending.pop(path, None)

                    elif elapsed >= _max_duration:
                        if not meta["search_done"]:
                            await _trigger_search(meta)
                            meta["search_done"] = True
                            meta["cycle_start"] = now
                            logger.info(
                                "Verifier: search triggered for %s (%s), new cycle started",
                                path,
                                meta.get("media_title", "?"),
                            )
                        else:
                            logger.warning(
                                "Not replaced: %s (%s) — marking as not_replaced",
                                path,
                                meta.get("media_title", "?"),
                            )
                            await _update_db_status(path, "non_remplacé", "verifier_fail")
                            _pending.pop(path, None)
                except Exception as e:
                    logger.error("Verifier error for %s: %s", path, e)
                    _pending.pop(path, None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Verifier loop crashed: %s — restarting", e)
            await asyncio.sleep(10)


def reload_config():
    global _interval, _max_duration, _enabled
    config = load_config()
    v = config.verifier
    _enabled = v.enabled
    _interval = float(v.interval_minutes * 60)
    _max_duration = float(v.max_duration_minutes * 60)


def start():
    global _task
    reload_config()
    if _task is None or _task.done():
        _task = asyncio.create_task(_check_loop())
        logger.info("Verifier started (interval=%.0fs, max=%.0fs)", _interval, _max_duration)


def stop():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        logger.info("Verifier stopped")
