import asyncio
import logging
import os

import aiosqlite

from app.database import DATABASE_PATH
from app.services.config_service import load_config
from app.services.filescanner import inspect_symlink

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None
_interval: float = 300
_enabled: bool = True
BATCH_DELAY = 0.05


def _check_symlink_valid(symlink_path: str, prefixes: list[str]) -> bool:
    try:
        if not os.path.islink(symlink_path):
            return False
        info = inspect_symlink(symlink_path, prefixes)
        return bool(info and not info["broken"] and info["matches_prefix"])
    except OSError:
        return False


async def _recheck_loop():
    logger.info("Rechecker loop started (interval=%.0fs)", _interval)
    while True:
        try:
            reload_config()
            if not _enabled:
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(_interval)

            config = load_config()
            radarr_prefixes = config.radarr.target_prefixes
            sonarr_prefixes = config.sonarr.target_prefixes
            if not radarr_prefixes and not sonarr_prefixes:
                continue

            try:
                db = await aiosqlite.connect(str(DATABASE_PATH))
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT id, symlink_path, source, media_title"
                    " FROM results"
                    " WHERE status IN ('détecté', 'surveillance', 'non_remplacé')"
                    " ORDER BY action_date ASC"
                )
                rows = [dict(r) for r in await cursor.fetchall()]
                await db.close()
            except Exception as e:
                logger.warning("Rechecker DB query failed: %s", e)
                continue

            if not rows:
                continue

            verified = 0
            for row in rows:
                try:
                    symlink_path = row.get("symlink_path", "")
                    source = row.get("source", "")
                    if not symlink_path or not source:
                        continue

                    prefixes = radarr_prefixes if source == "radarr" else sonarr_prefixes
                    if not prefixes:
                        continue

                    if not _check_symlink_valid(symlink_path, prefixes):
                        await asyncio.sleep(BATCH_DELAY)
                        continue

                    db2 = await aiosqlite.connect(str(DATABASE_PATH))
                    try:
                        await db2.execute(
                            "UPDATE results SET status = 'remplacé',"
                            " action = 'auto_verified',"
                            " action_date = datetime('now')"
                            " WHERE id = ? AND status IN ('détecté','surveillance','non_remplacé')",
                            (row["id"],),
                        )
                        await db2.execute(
                            "UPDATE results SET status = 'remplacé',"
                            " action = 'auto_verified_sibling',"
                            " action_date = datetime('now')"
                            " WHERE symlink_path = ? AND source = ?"
                            " AND id != ? AND status IN ('détecté','surveillance','non_remplacé')",
                            (symlink_path, source, row["id"]),
                        )
                        await db2.commit()
                    finally:
                        await db2.close()

                    verified += 1
                    title = row.get("media_title") or symlink_path
                    logger.info("Rechecker: %s → remplacé (%s)", symlink_path, title)

                    await asyncio.sleep(BATCH_DELAY)

                except Exception as e:
                    logger.warning("Rechecker error for id=%d: %s", row.get("id"), e)

            if verified:
                logger.info("Rechecker: %d symlinks vérifiés comme remplacés", verified)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Rechecker loop crashed: %s — restarting", e)
            await asyncio.sleep(10)


def reload_config():
    global _interval, _enabled
    config = load_config()
    r = config.rechecker
    _enabled = r.enabled
    _interval = float(r.interval_minutes * 60)


def start():
    global _task
    reload_config()
    if _task is None or _task.done():
        _task = asyncio.create_task(_recheck_loop())
        logger.info("Rechecker started (interval=%.0fs)", _interval)


def stop():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
        logger.info("Rechecker stopped")
