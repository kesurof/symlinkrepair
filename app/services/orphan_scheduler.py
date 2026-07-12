import asyncio
import logging
from datetime import datetime, timezone

import aiosqlite

from app.database import DATABASE_PATH
from app.services.alldebrid import is_hash_name
from app.services.config_service import load_config
from app.services.discord import send_webhook

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _delete_orphans_from_result(api_key, result, rate_limit):
    from app.services.alldebrid import AllDebridAPI
    deleted = 0
    errors = 0
    async with AllDebridAPI(api_key, rate_limit) as api:
        for cand in result.orphans:
            try:
                ok = await api.delete_magnet(cand.magnet_id)
                if ok:
                    deleted += 1
                    await asyncio.sleep(rate_limit)
                else:
                    errors += 1
            except Exception as e:
                logger.warning("Delete failed for %s: %s", cand.magnet_id, e)
                errors += 1
    return deleted, errors


async def _run_orphan_scan():
    config = load_config()
    ad = config.alldebrid
    if not ad.enabled or not ad.api_key or not ad.medias_base:
        logger.debug("Orphan scheduler: not enabled or missing config")
        return

    prefixes = []
    for src in (config.radarr, config.sonarr):
        prefixes.extend(src.target_prefixes)
    if not prefixes:
        logger.warning("Orphan scheduler: no target_prefixes configured")
        return

    from app.services.orphan_detector import OrphanDetector
    detector = OrphanDetector(
        medias_base=ad.medias_base,
        target_prefixes=list(set(prefixes)),
        api_key=ad.api_key,
        min_age_hours=ad.min_age_hours,
        rate_limit=ad.rate_limit,
    )

    result = await detector.run()

    db = await aiosqlite.connect(str(DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    try:
        cursor = await db.execute(
            "INSERT INTO scans"
            " (source, mode, status, total, broken, processed, summary, completed_at)"
            " VALUES (?, ?, ?, ?, ?, 0, ?, datetime('now'))",
            (
                "alldebrid",
                "auto",
                "completed",
                result.total_magnets,
                result.orphan_count,
                (
                    f"{result.used_count} used, {result.protected_count} protected,"
                    f" {result.orphan_count} orphans"
                ),
            ),
        )
        scan_id = cursor.lastrowid

        for cand in result.orphans + result.protected + result.used:
            await db.execute(
            "INSERT INTO orphan_magnets"
            " (scan_id, magnet_id, primary_name, status, age_hours, is_hash)"
            " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    scan_id,
                    cand.magnet_id,
                    cand.primary_name,
                    cand.status,
                    cand.age_hours,
                    1 if is_hash_name(cand.primary_name) else 0,
                ),
            )

        if result.orphans:
            logger.info("Auto-deleting %d orphans...", result.orphan_count)
            deleted, errs = await _delete_orphans_from_result(ad.api_key, result, ad.rate_limit)
            await db.execute(
                "UPDATE scans SET processed = ? WHERE id = ?",
                (deleted, scan_id),
            )
            for cand in result.orphans:
                await db.execute(
                    "UPDATE orphan_magnets SET status = ?, action = 'deleted',"
                    " action_date = datetime('now')"
                    " WHERE scan_id = ? AND magnet_id = ?",
                    ("supprimé", scan_id, cand.magnet_id),
                )
            logger.info("Auto-delete done: %d deleted, %d errors", deleted, errs)

        await db.commit()

        if result.orphan_count > 0 and config.discord.enabled and config.discord.webhook:
            payload = {
                "embeds": [{
                    "title": "🤖 Nettoyage AllDebrid automatique",
                    "description": f"{result.orphan_count} magnets orphelins supprimés",
                    "color": 0x57F287,
                    "fields": [
                        {
                            "name": "Total magnets",
                            "value": str(result.total_magnets),
                            "inline": True,
                        },
                        {"name": "Utilisés", "value": str(result.used_count), "inline": True},
                        {"name": "Protégés", "value": str(result.protected_count), "inline": True},
                        {
                            "name": "Orphelins supprimés",
                            "value": str(result.orphan_count),
                            "inline": True,
                        },
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }]
            }
            await send_webhook(config.discord.webhook, payload)

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

    db = await aiosqlite.connect(str(DATABASE_PATH))
    try:
        cursor = await db.execute(
            "SELECT created_at FROM scans WHERE source = 'alldebrid'"
            " AND created_at >= DATE('now') ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return True
        last = datetime.fromisoformat(row[0])
        return last.date() < now.date()
    finally:
        await db.close()


async def _orphan_scheduler_loop():
    logger.info("Orphan scheduler background loop started")
    while True:
        try:
            config = load_config()
            ad = config.alldebrid
            if ad.enabled and ad.api_key and ad.medias_base:
                if await _should_run_today(ad.schedule_time):
                    logger.info("Triggering orphan scan (scheduled time=%s)", ad.schedule_time)
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
