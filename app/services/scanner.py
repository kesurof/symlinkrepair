import asyncio
import json
import logging
from datetime import datetime

from app.services import filescanner
from app.services.config_service import load_config
from app.services.radarr import (
    copy_database as radarr_copy_db,
)
from app.services.radarr import (
    load_movie_records,
)
from app.services.sonarr import (
    copy_database as sonarr_copy_db,
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


async def _run_scan(source: str, mode: str) -> dict:
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
        return {"status": "error", "error": "Configuration incomplète"}

    results, total, matching, broken = filescanner.scan_library_roots(
        cfg.library_roots, cfg.target_prefixes
    )

    db_path = db_copy_fn(cfg.container)
    records = {}
    if db_path:
        records = records_fn(db_path)
    else:
        logger.warning("Could not copy database for %s", source)

    targets = []
    affected_titles = set()
    for r in results:
        record = records.get(r["symlink_path"])
        if record:
            r["file_id"] = record.get("movie_file_id") or record.get("episode_file_id")
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
        r["status"] = "detected"
        targets.append(r)

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


async def start_scan(source: str, mode: str = "simulate") -> dict:
    lock = _radarr_lock if source == "radarr" else _sonarr_lock
    if lock.locked():
        return {"status": "error", "error": "Un scan est déjà en cours"}

    async with lock:
        task = asyncio.create_task(_run_scan(source, mode))
        _active_tasks[source] = task
        result = await task
        _active_tasks.pop(source, None)
        return result


async def get_scan_status(source: str) -> dict:
    running = is_running(source)
    return {"source": source, "running": running}
