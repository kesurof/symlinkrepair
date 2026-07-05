import logging
import os

from aiosqlite import Connection

from app.services.config_service import load_config
from app.services.radarr import (
    delete_movie_file,
    refresh_movie,
    search_movies,
)
from app.services.sonarr import (
    delete_episode_file,
    rescan_series,
    search_season,
)

logger = logging.getLogger(__name__)


async def _process_single(result: dict, config) -> dict:
    source = result.get("source", "")
    file_id = result.get("file_id")
    symlink_path = result.get("symlink_path", "")
    action_log = {"api_delete": False, "symlink_removed": False, "refresh": False, "search": False}

    if not file_id:
        return {"ok": False, "error": "Aucun file_id associé", "actions": action_log}

    if source == "radarr":
        cfg = config.radarr
        if not cfg.api_key:
            return {"ok": False, "error": "Clé API Radarr non configurée", "actions": action_log}

        ok = await delete_movie_file(cfg.url, cfg.api_key, file_id)
        action_log["api_delete"] = ok

        if ok:
            movie_id = result.get("movie_id")
            if movie_id and config.defaults.rescan:
                action_log["refresh"] = await refresh_movie(cfg.url, cfg.api_key, movie_id)
            if movie_id and config.defaults.search:
                action_log["search"] = await search_movies(cfg.url, cfg.api_key, [movie_id])

    elif source == "sonarr":
        cfg = config.sonarr
        if not cfg.api_key:
            return {"ok": False, "error": "Clé API Sonarr non configurée", "actions": action_log}

        ok = await delete_episode_file(cfg.url, cfg.api_key, file_id)
        action_log["api_delete"] = ok

        if ok:
            series_id = result.get("series_id")
            season = result.get("season")
            if series_id and config.defaults.rescan:
                action_log["refresh"] = await rescan_series(cfg.url, cfg.api_key, series_id)
            if series_id and season and config.defaults.search:
                action_log["search"] = await search_season(cfg.url, cfg.api_key, series_id, season)

    if action_log["api_delete"] and not config.defaults.keep_symlinks and symlink_path:
        try:
            if os.path.islink(symlink_path):
                os.unlink(symlink_path)
                action_log["symlink_removed"] = True
        except OSError as e:
            logger.warning("Failed to remove symlink %s: %s", symlink_path, e)

    return {"ok": action_log["api_delete"], "actions": action_log}


async def process_result(result: dict) -> dict:
    config = load_config()
    return await _process_single(result, config)


async def process_result_season(result: dict, db: Connection) -> dict:
    config = load_config()
    series_id = result.get("series_id")
    season = result.get("season")
    result_id = result.get("id")

    if not series_id or season is None:
        return {"ok": False, "error": "Aucune series_id/saison", "actions": {}}

    cursor = await db.execute(
        "SELECT * FROM results WHERE source = 'sonarr' AND series_id = ? AND season = ?"
        " AND status = 'detected' AND id != ?",
        (series_id, season, result_id),
    )
    rows = await cursor.fetchall()
    all_results = [dict(result)] + [dict(r) for r in rows]

    ok_count = 0
    total_actions = {"api_delete": False, "symlink_removed": False, "refresh": False, "search": False}

    for r in all_results:
        outcome = await _process_single(r, config)
        if outcome["ok"]:
            ok_count += 1
            await db.execute(
                "UPDATE results SET status = 'processed', action = 'api_delete',"
                " action_date = datetime('now') WHERE id = ?",
                (r["id"],),
            )
        else:
            await db.execute(
                "UPDATE results SET status = 'failed', action = 'api_error',"
                " action_date = datetime('now') WHERE id = ?",
                (r["id"],),
            )
        for k in total_actions:
            if outcome.get("actions", {}).get(k):
                total_actions[k] = True

    await db.commit()

    if ok_count > 0 and config.defaults.rescan:
        total_actions["refresh"] = await rescan_series(
            config.sonarr.url, config.sonarr.api_key, series_id
        )
    if ok_count > 0 and season is not None and config.defaults.search:
        total_actions["search"] = await search_season(
            config.sonarr.url, config.sonarr.api_key, series_id, season
        )

    return {"ok": ok_count > 0, "error": "", "actions": total_actions, "processed": ok_count, "total": len(all_results)}
