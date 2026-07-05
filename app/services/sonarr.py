import logging
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


async def test_connection(url: str, api_key: str) -> dict:
    if not url or not api_key:
        return {"ok": False, "error": "URL ou clé API manquante"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/api/v3/system/status",
                headers={"X-Api-Key": api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"ok": True, "version": data.get("version", "?")}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def copy_database(container: str) -> str | None:
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        subprocess.run(
            ["docker", "cp", f"{container}:/config/sonarr.db", tmp.name],
            capture_output=True,
            timeout=30,
        )
        return tmp.name
    except Exception as e:
        logger.error("Failed to copy Sonarr DB: %s", e)
        return None


def load_episode_records(db_path: str) -> dict[str, dict]:
    records_by_path: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT
                ef.Id AS episode_file_id,
                ef.SeriesId AS series_id,
                ef.RelativePath AS relative_path,
                e.SeasonNumber AS season,
                e.EpisodeNumber AS episode,
                s.Path AS series_path,
                s.Tags AS tags,
                sm.Title AS title
            FROM EpisodeFiles ef
            JOIN Episodes e ON e.EpisodeFileId = ef.Id
            JOIN Series s ON s.Id = ef.SeriesId
            LEFT JOIN SeriesMetadata sm ON sm.Id = s.SeriesMetadataId
        """)
        for row in cursor.fetchall():
            full_path = str(Path(str(row["series_path"])) / str(row["relative_path"]))
            records_by_path[full_path] = dict(row)
        conn.close()
    except Exception as e:
        logger.error("Failed to load Sonarr records: %s", e)
    return records_by_path


async def delete_episode_file(url: str, api_key: str, file_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{url.rstrip('/')}/api/v3/episodefile/{file_id}",
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error("Failed to delete episode file %s: %s", file_id, e)
        return False


async def rescan_series(url: str, api_key: str, series_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json={"name": "RescanSeries", "seriesId": series_id},
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 201
    except Exception as e:
        logger.error("Failed to rescan series %s: %s", series_id, e)
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
            return resp.status_code == 201
    except Exception as e:
        logger.error("Failed to search season %s/%s: %s", series_id, season, e)
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
