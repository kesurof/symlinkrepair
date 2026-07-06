import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from app.services import filescanner
from app.services.config_service import load_config
from app.services.radarr import (
    copy_database_from_container as radarr_copy_db,
)
from app.services.radarr import (
    load_movie_records,
)
from app.services.sonarr import (
    copy_database_from_container as sonarr_copy_db,
)
from app.services.sonarr import (
    load_episode_records,
)

logger = logging.getLogger(__name__)

_radarr_lock = asyncio.Lock()
_sonarr_lock = asyncio.Lock()
_active_tasks: dict[str, asyncio.Task] = {}


def is_running(source: str) -> bool:
    task = _active_tasks.get(source)
    return task is not None and not task.done()


async def _run_scan(source: str, mode: str, limit: int = 0) -> dict:
    config = load_config()
    if source == "radarr":
        cfg = config.radarr
        records_fn = load_movie_records
        db_copy_fn = radarr_copy_db
    else:
        cfg = config.sonarr
        records_fn = load_episode_records
        db_copy_fn = sonarr_copy_db

    if not cfg.library_roots or not cfg.target_prefixes:
        logger.warning("Scan aborted: incomplete config for %s", source)
        return {"status": "error", "error": "Configuration incomplète"}

    limit = limit or config.defaults.limit
    logger.info("Starting scan: source=%s mode=%s limit=%d", source, mode, limit)
    results, total, matching, broken = filescanner.scan_library_roots(
        cfg.library_roots, cfg.target_prefixes, limit
    )
    logger.info(
        "Filesystem scan done: source=%s total=%d matching=%d broken=%d",
        source, total, matching, broken,
    )

    db_path = db_copy_fn(cfg.container)
    records = {}
    if db_path:
        records = records_fn(db_path)
    else:
        logger.warning("Could not copy database for %s", source)

    def find_record(symlink_path: str) -> dict | None:
        record = records.get(symlink_path)
        if record:
            return record
        basename = Path(symlink_path).name
        for path, rec in records.items():
            if Path(path).name == basename:
                return rec
        return None

    targets = []
    affected_titles = set()
    for r in results:
        record = find_record(r["symlink_path"])
        if record:
            r["file_id"] = record.get("movie_file_id") or record.get("episode_file_id")
            r["movie_id"] = record.get("movie_id")
            r["series_id"] = record.get("series_id")
            r["media_title"] = record.get("title", "")
            r["media_type"] = "movie" if source == "radarr" else "episode"
            r["season"] = record.get("season")
            r["episode"] = record.get("episode")
            r["tags"] = json.dumps(record.get("tags", []))
            if r.get("media_title"):
                affected_titles.add(r["media_title"])
        else:
            r["media_title"] = ""
            r["media_type"] = ""
            r["tags"] = "[]"
        r["source"] = source
        r["detection"] = "broken_symlink"
        r["status"] = "détecté"
        targets.append(r)

    if targets:
        logger.info("Broken symlinks for %s:", source)
        for t in targets:
            logger.info("  %s (%s)", t["symlink_path"], t.get("media_title") or "?")

    logger.info(
        "Scan completed: source=%s broken=%d matched=%d affected_titles=%d",
        source, broken, len(targets), len(affected_titles),
    )

    return {
        "status": "completed",
        "source": source,
        "mode": mode,
        "total": total,
        "matching": matching,
        "broken": broken,
        "targets": targets,
        "affected_count": len(affected_titles),
        "timestamp": datetime.now().isoformat(),
    }


async def start_scan(source: str, mode: str = "simulate", limit: int = 0) -> dict:
    lock = _radarr_lock if source == "radarr" else _sonarr_lock
    if lock.locked():
        return {"status": "error", "error": "Un scan est déjà en cours"}

    async with lock:
        task = asyncio.create_task(_run_scan(source, mode, limit))
        _active_tasks[source] = task
        result = await task
        _active_tasks.pop(source, None)
        return result


async def get_scan_status(source: str) -> dict:
    running = is_running(source)
    return {"source": source, "running": running}
