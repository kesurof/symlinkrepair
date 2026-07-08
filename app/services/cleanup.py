import asyncio
import logging
import os

from aiosqlite import Connection

from app.services.config_service import load_config
from app.services.filescanner import inspect_symlink
from app.services.radarr import delete_movie_file, refresh_movie, search_movies
from app.services.sonarr import delete_episode_file, rescan_series, search_season
from app.services.verifier import add as verifier_add

logger = logging.getLogger(__name__)

DELETE_DELAY = 0.05
COMMAND_DELAY = 0.10


def _unlink_symlink(symlink_path: str, keep_symlinks: bool) -> bool:
    if keep_symlinks or not symlink_path or not os.path.islink(symlink_path):
        return False
    try:
        os.unlink(symlink_path)
        logger.info("Symlink removed: %s", symlink_path)
        return True
    except OSError as e:
        logger.warning("Failed to remove symlink %s: %s", symlink_path, e)
        return False


def _source_cfg(config, source: str):
    if source == "radarr":
        return config.radarr
    return config.sonarr


def _check_symlink(result: dict, prefixes: list[str]) -> dict | None:
    symlink_path = result.get("symlink_path", "")
    if not symlink_path or not os.path.islink(symlink_path):
        return None
    try:
        return inspect_symlink(symlink_path, prefixes)
    except OSError:
        return None


async def _delete_one(result: dict, config, delete_season: bool = False) -> dict:
    source = result.get("source", "")
    file_id = result.get("file_id")
    action = {
        "api_delete": False,
        "symlink_removed": False,
        "refresh": False,
        "search": False,
        "skipped": "",
        "auto_fixed": False,
    }

    if not file_id:
        action["skipped"] = "no_file_id"
        return action

    cfg = _source_cfg(config, source)
    if not cfg.api_key:
        action["skipped"] = "missing_api_key"
        return action

    info = _check_symlink(result, cfg.target_prefixes)
    if info:
        if not info["matches_prefix"]:
            action["skipped"] = "target_not_allowed"
            return action
        if not delete_season and not info["broken"]:
            action["auto_fixed"] = True
            return action

    if source == "radarr":
        action["api_delete"] = await delete_movie_file(cfg.url, cfg.api_key, file_id)
    elif source == "sonarr":
        action["api_delete"] = await delete_episode_file(cfg.url, cfg.api_key, file_id)

    if action["api_delete"]:
        action["symlink_removed"] = _unlink_symlink(
            result.get("symlink_path", ""),
            config.defaults.keep_symlinks,
        )
        symlink_path = result.get("symlink_path", "?")
        title = result.get("media_title") or "?"
        logger.info(
            "Deleted %s file_id=%d title=%s path=%s",
            source,
            file_id,
            title,
            symlink_path,
        )
        verifier_add(
            symlink_path=symlink_path,
            source=source,
            file_id=file_id,
            media_title=title,
            series_id=result.get("series_id"),
            movie_id=result.get("movie_id"),
            season=result.get("season"),
            result_id=result.get("id"),
        )
    elif not action.get("skipped"):
        action["skipped"] = "api_failed"
        logger.warning("Delete failed for %s file_id=%d", source, file_id)

    return action


async def process_single(result: dict) -> dict:
    config = load_config()
    action = await _delete_one(result, config)
    if action.get("auto_fixed"):
        logger.info(
            "Auto-fixed (symlink already valid): %s",
            result.get("symlink_path", "?"),
        )
        return {"ok": True, "auto_fixed": True, "actions": action}
    if not action["api_delete"]:
        return {"ok": False, "error": action.get("skipped", "delete_failed"), "actions": action}

    cfg = _source_cfg(config, result.get("source", ""))
    if config.defaults.rescan:
        await asyncio.sleep(COMMAND_DELAY)
        if result.get("source") == "radarr" and result.get("movie_id"):
            action["refresh"] = await refresh_movie(cfg.url, cfg.api_key, result["movie_id"])
        elif result.get("source") == "sonarr" and result.get("series_id"):
            action["refresh"] = await rescan_series(cfg.url, cfg.api_key, result["series_id"])

    if config.defaults.search:
        await asyncio.sleep(COMMAND_DELAY)
        if result.get("source") == "radarr" and result.get("movie_id"):
            action["search"] = await search_movies(cfg.url, cfg.api_key, [result["movie_id"]])
        elif (
            result.get("source") == "sonarr"
            and result.get("series_id")
            and (result.get("season") is not None)
        ):
            action["search"] = await search_season(
                cfg.url,
                cfg.api_key,
                result["series_id"],
                result["season"],
            )

    logger.info(
        "Process single result %s: ok=True api_delete=%s symlink_removed=%s refresh=%s search=%s",
        result.get("symlink_path", "?"),
        action.get("api_delete"),
        action.get("symlink_removed"),
        action.get("refresh"),
        action.get("search"),
    )
    return {"ok": True, "actions": action}


async def process_season(result: dict, db: Connection, scan_id: int) -> dict:
    config = load_config()
    if result.get("source") != "sonarr":
        return {"ok": False, "error": "Mode saison réservé à Sonarr", "actions": {}}

    series_id = result.get("series_id")
    season = result.get("season")
    if not series_id or season is None:
        return {"ok": False, "error": "Aucune series_id/saison", "actions": {}}

    cursor = await db.execute(
        "SELECT * FROM results"
        " WHERE series_id = ? AND season = ? AND source = 'sonarr'"
        " AND status NOT IN ('remplacé','ignoré')",
        (series_id, season),
    )
    all_results = [dict(r) for r in await cursor.fetchall()]

    actions = {"api_delete": False, "symlink_removed": False, "refresh": False, "search": False}
    logger.info(
        "Season cleanup: series=%s season=%s total=%d",
        series_id,
        season,
        len(all_results),
    )

    if not all_results:
        return {
            "ok": False,
            "error": "Aucun résultat trouvé pour cette saison",
            "actions": actions,
            "processed": 0,
            "total": 0,
            "search_triggered": False,
        }

    targets = [r for r in all_results if r.get("file_id") is not None]
    no_file = [r for r in all_results if r.get("file_id") is None]

    deleted = 0
    failed_skipped = []
    for target in targets:
        outcome = await _delete_one(target, config, delete_season=True)
        if outcome["api_delete"]:
            deleted += 1
            actions["api_delete"] = True
            actions["symlink_removed"] = actions["symlink_removed"] or outcome["symlink_removed"]
            await db.execute(
                "UPDATE results SET status = 'surveillance', action = 'api_delete',"
                " search_count = search_count + 1, action_date = datetime('now')"
                " WHERE id = ?",
                (target["id"],),
            )
        else:
            skip_reason = outcome.get("skipped", "api_failed")
            failed_skipped.append(skip_reason)
            await db.execute(
                "UPDATE results SET status = 'échoué', action = 'api_error',"
                " action_date = datetime('now') WHERE id = ?",
                (target["id"],),
            )
        await asyncio.sleep(DELETE_DELAY)

    for r in no_file:
        await db.execute(
            "UPDATE results SET status = 'surveillance', action = 'recheck',"
            " action_date = datetime('now') WHERE id = ?",
            (r["id"],),
        )

    await db.commit()

    if config.defaults.rescan:
        await asyncio.sleep(COMMAND_DELAY)
        actions["refresh"] = await rescan_series(
            config.sonarr.url,
            config.sonarr.api_key,
            series_id,
        )

    if config.defaults.search:
        await asyncio.sleep(COMMAND_DELAY)
        actions["search"] = await search_season(
            config.sonarr.url,
            config.sonarr.api_key,
            series_id,
            season,
        )

    search_triggered = actions["refresh"] or actions["search"]

    error_msg = ""
    if not search_triggered and deleted == 0 and failed_skipped:
        skipped_counts = {}
        for s in failed_skipped:
            skipped_counts[s] = skipped_counts.get(s, 0) + 1
        reasons = ", ".join(f"{c}x {r}" for r, c in skipped_counts.items())
        error_msg = f"Tous les épisodes ont échoué : {reasons}"

    logger.info(
        "Season cleanup done: series=%s season=%s deleted=%d total=%d failed=%s search=%s",
        series_id,
        season,
        deleted,
        len(all_results),
        failed_skipped,
        search_triggered,
    )
    return {
        "ok": deleted > 0 or search_triggered,
        "error": error_msg,
        "actions": actions,
        "processed": deleted,
        "total": len(all_results),
        "search_triggered": search_triggered,
    }


async def process_all_detected(source: str, db: Connection, scan_id: int) -> dict:
    config = load_config()
    cursor = await db.execute(
        "SELECT * FROM results WHERE scan_id = ? AND source = ?"
        " AND status IN ('détecté','surveillance') AND file_id IS NOT NULL",
        (scan_id, source),
    )
    rows = [dict(row) for row in await cursor.fetchall()]
    logger.info(
        "Batch cleanup starting: source=%s scan_id=%d results=%d",
        source,
        scan_id,
        len(rows),
    )

    deleted = 0
    failed = 0
    affected_movies: list[int] = []
    affected_series: set[int] = set()
    affected_seasons: set[tuple[int, int]] = set()

    for row in rows:
        outcome = await _delete_one(row, config)
        if outcome["api_delete"]:
            deleted += 1
            await db.execute(
                "UPDATE results SET status = 'surveillance', action = 'api_delete',"
                " action_date = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            if source == "radarr":
                movie_id = row.get("movie_id")
                if movie_id and movie_id not in affected_movies:
                    affected_movies.append(movie_id)
            elif source == "sonarr":
                series_id = row.get("series_id")
                season = row.get("season")
                if series_id:
                    affected_series.add(series_id)
                if series_id and season is not None:
                    affected_seasons.add((series_id, season))
        else:
            failed += 1
            await db.execute(
                "UPDATE results SET status = 'échoué', action = 'api_error',"
                " action_date = datetime('now') WHERE id = ?",
                (row["id"],),
            )

        await asyncio.sleep(DELETE_DELAY)

    await db.commit()

    if deleted > 0 and config.defaults.rescan:
        if source == "radarr":
            for movie_id in affected_movies:
                await asyncio.sleep(COMMAND_DELAY)
                await refresh_movie(config.radarr.url, config.radarr.api_key, movie_id)
        elif source == "sonarr":
            for series_id in sorted(affected_series):
                await asyncio.sleep(COMMAND_DELAY)
                await rescan_series(config.sonarr.url, config.sonarr.api_key, series_id)

    if deleted > 0 and config.defaults.search:
        if source == "radarr" and affected_movies:
            await asyncio.sleep(COMMAND_DELAY)
            await search_movies(config.radarr.url, config.radarr.api_key, affected_movies)
            logger.info(
                "Search triggered for %d Radarr movies: %s",
                len(affected_movies),
                affected_movies,
            )
        elif source == "sonarr":
            for series_id, season in sorted(affected_seasons):
                await asyncio.sleep(COMMAND_DELAY)
                await search_season(config.sonarr.url, config.sonarr.api_key, series_id, season)

    logger.info(
        "Batch cleanup done: source=%s scan_id=%d deleted=%d failed=%d total=%d",
        source,
        scan_id,
        deleted,
        failed,
        len(rows),
    )
    return {"deleted": deleted, "failed": failed, "total": len(rows)}
