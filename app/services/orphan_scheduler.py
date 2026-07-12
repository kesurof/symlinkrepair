import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.database import DATABASE_PATH
from app.services.alldebrid import is_hash_name
from app.services.config_service import load_config
from app.services.discord import send_webhook

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_STATE_FILE = Path(DATABASE_PATH).parent / ".orphan_auto_state"


def _collect_fallback_prefixes(config) -> list[str]:
    prefixes = set()
    for src in (config.radarr, config.sonarr):
        prefixes.update(src.target_prefixes)
    return list(prefixes)


async def _delete_orphans_from_instance(inst, magnet_ids):
    from app.services.alldebrid import AllDebridAPI

    deleted = 0
    errors = 0
    if not magnet_ids:
        return deleted, errors
    async with AllDebridAPI(inst.api_key, inst.rate_limit) as api:
        for mid in magnet_ids:
            try:
                ok = await api.delete_magnet(mid)
                if ok:
                    deleted += 1
                    await asyncio.sleep(inst.rate_limit)
                else:
                    errors += 1
            except Exception as e:
                logger.warning("Delete failed for %s: %s", mid, e)
                errors += 1
    return deleted, errors


async def _run_orphan_scan():
    config = load_config()
    active = [i for i in config.alldebrid.instances if i.enabled and i.api_key and i.library_roots]
    if not active:
        logger.debug("Orphan scheduler: no active instances")
        return

    fallback = _collect_fallback_prefixes(config)
    from app.services.orphan_detector import OrphanDetector

    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("DELETE FROM orphan_magnets")
        await db.commit()

        for inst in active:
            detector = OrphanDetector(inst, fallback_prefixes=fallback)
            result = await detector.run()
            if result.total_magnets == 0:
                continue

            orphan_ids = []
            for cand in result.orphans + result.protected + result.used:
                await db.execute(
                    "INSERT INTO orphan_magnets"
                    " (magnet_id, primary_name, status, age_hours, is_hash, notes)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        cand.magnet_id,
                        cand.primary_name,
                        cand.status,
                        cand.age_hours,
                        1 if is_hash_name(cand.primary_name) else 0,
                        inst.name,
                    ),
                )
                if cand.status == "orphan":
                    orphan_ids.append(cand.magnet_id)

            if orphan_ids:
                logger.info(
                    "[%s] Auto-deleting %d orphans...",
                    inst.name,
                    len(orphan_ids),
                )
                deleted, errs = await _delete_orphans_from_instance(inst, orphan_ids)
                await db.execute(
                    "UPDATE orphan_magnets SET status = 'supprimé', action = 'deleted',"
                    " action_date = datetime('now')"
                    " WHERE notes = ? AND magnet_id IN (" + ",".join("?" for _ in orphan_ids) + ")",
                    (inst.name, *orphan_ids),
                )
                logger.info(
                    "[%s] Auto-delete done: %d deleted, %d errors",
                    inst.name,
                    deleted,
                    errs,
                )

            await db.commit()

            if result.orphan_count > 0 and config.discord.enabled and config.discord.webhook:
                payload = {
                    "embeds": [
                        {
                            "title": f"🤖 AllDebrid auto — {inst.name}",
                            "description": f"{result.orphan_count} magnets orphelins supprimés",
                            "color": 0x57F287,
                            "fields": [
                                {
                                    "name": "Total magnets",
                                    "value": str(result.total_magnets),
                                    "inline": True,
                                },
                                {
                                    "name": "Utilisés",
                                    "value": str(result.used_count),
                                    "inline": True,
                                },
                                {
                                    "name": "Protégés",
                                    "value": str(result.protected_count),
                                    "inline": True,
                                },
                                {
                                    "name": "Orphelins supprimés",
                                    "value": str(result.orphan_count),
                                    "inline": True,
                                },
                            ],
                            "timestamp": datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z"),
                        }
                    ]
                }
                await send_webhook(config.discord.webhook, payload)

        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(datetime.now().strftime("%Y-%m-%d"))

    finally:
        await db.close()


async def _should_run_today(schedule_time: str) -> bool:
    now = datetime.now()
    try:
        parts = schedule_time.strip().split(":")
        target_hour = int(parts[0])
        target_minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return False

    if now.hour != target_hour or now.minute != target_minute:
        return False

    try:
        last = _STATE_FILE.read_text().strip()
        return last != now.strftime("%Y-%m-%d")
    except (FileNotFoundError, OSError):
        return True


async def _orphan_scheduler_loop():
    logger.info("Orphan scheduler background loop started")
    while True:
        try:
            config = load_config()
            ad = config.alldebrid
            if ad.instances and ad.auto_enabled:
                if await _should_run_today(ad.schedule_time):
                    logger.info(
                        "Triggering orphan scan (scheduled time=%s)",
                        ad.schedule_time,
                    )
                    await _run_orphan_scan()
        except Exception as e:
            logger.error("Orphan scheduler loop error: %s", e)
        await asyncio.sleep(60)


def start():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_orphan_scheduler_loop())
        logger.info("Orphan scheduler started")


def stop():
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Orphan scheduler stopped")
