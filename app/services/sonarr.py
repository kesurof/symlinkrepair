import logging
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


def copy_database(container: str, db_name: str) -> str | None:
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        subprocess.run(
            ["docker", "cp", f"{container}:/config/{db_name}", tmp.name],
            capture_output=True,
            timeout=30,
        )
        logger.info("Copied %s from container %s to %s", db_name, container, tmp.name)
        return tmp.name
    except Exception as e:
        logger.error("Failed to copy %s from %s: %s", db_name, container, e)
        if tmp and Path(tmp.name).exists():
            Path(tmp.name).unlink(missing_ok=True)
        return None


def copy_database_from_container(container: str) -> str | None:
    return copy_database(container, "sonarr.db")


def load_episode_records(db_path: str) -> dict[str, dict]:
    records_by_path: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT
                ef.Id AS episode_file_id,
                ef.SeriesId AS series_id,
                ef.SeasonNumber AS season,
                (s.Path || '/' || ef.RelativePath) AS full_path,
                s.Title AS title,
                s.Tags AS tags
            FROM EpisodeFiles ef
            JOIN Series s ON s.Id = ef.SeriesId
        """)
        for row in cursor.fetchall():
            d = dict(row)
            fp = d.get("full_path", "")
            if fp:
                records_by_path[fp] = d
        conn.close()
        logger.info("Loaded %d Sonarr episode records", len(records_by_path))
    except Exception as e:
        logger.error("Failed to load Sonarr records: %s", e)
    finally:
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception:
            pass
    return records_by_path


async def delete_episode_file(url: str, api_key: str, file_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{url.rstrip('/')}/api/v3/episodefile/{file_id}",
                headers={"X-Api-Key": api_key},
            )
            ok = resp.status_code == 200
            if ok:
                logger.info("Deleted episode file %d", file_id)
            else:
                logger.warning(
                    "Failed to delete episode file %d: HTTP %d",
                    file_id, resp.status_code,
                )
            return ok
    except Exception as e:
        logger.error("Failed to delete episode file %d: %s", file_id, e)
        return False


async def rescan_series(url: str, api_key: str, series_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json={"name": "RescanSeries", "seriesId": series_id},
                headers={"X-Api-Key": api_key},
            )
            ok = resp.status_code == 201
            if ok:
                logger.info("Rescan command submitted for series %d", series_id)
            else:
                logger.warning(
                    "Rescan command failed for series %d: HTTP %d",
                    series_id, resp.status_code,
                )
            return ok
    except Exception as e:
        logger.error("Rescan command failed for series %d: %s", series_id, e)
        return False


async def search_season(url: str, api_key: str, series_id: int, season: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json={
                    "name": "SeasonSearch",
                    "seriesId": series_id,
                    "seasonNumber": season,
                },
                headers={"X-Api-Key": api_key},
            )
            ok = resp.status_code == 201
            if ok:
                logger.info("Search command submitted for season %d/%d", series_id, season)
            else:
                logger.warning(
                    "Search command failed for season %d/%d: HTTP %d",
                    series_id, season, resp.status_code,
                )
            return ok
    except Exception as e:
        logger.error("Search command failed for season %d/%d: %s", series_id, season, e)
        return False


async def fetch_tags(url: str, api_key: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/api/v3/tag",
                headers={"X-Api-Key": api_key},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.error("Failed to fetch Sonarr tags: %s", e)
    return []
