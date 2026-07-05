import logging
import os

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


async def process_result(result: dict) -> dict:
    source = result.get("source", "")
    config = load_config()
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
            movie_id = result.get("file_id")
            if config.defaults.rescan:
                action_log["refresh"] = await refresh_movie(cfg.url, cfg.api_key, movie_id)
            if config.defaults.search:
                action_log["search"] = await search_movies(cfg.url, cfg.api_key, [movie_id])

    elif source == "sonarr":
        cfg = config.sonarr
        if not cfg.api_key:
            return {"ok": False, "error": "Clé API Sonarr non configurée", "actions": action_log}

        ok = await delete_episode_file(cfg.url, cfg.api_key, file_id)
        action_log["api_delete"] = ok

        if ok:
            series_id = result.get("file_id")
            season = result.get("season")
            if config.defaults.rescan and series_id:
                action_log["refresh"] = await rescan_series(cfg.url, cfg.api_key, series_id)
            if config.defaults.search and series_id and season:
                action_log["search"] = await search_season(cfg.url, cfg.api_key, series_id, season)

    if not config.defaults.keep_symlinks and symlink_path:
        try:
            if os.path.islink(symlink_path):
                os.unlink(symlink_path)
                action_log["symlink_removed"] = True
        except OSError as e:
            logger.warning("Failed to remove symlink %s: %s", symlink_path, e)

    return {"ok": action_log["api_delete"], "actions": action_log}
