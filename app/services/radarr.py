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
            ["docker", "cp", f"{container}:/config/radarr.db", tmp.name],
            capture_output=True,
            timeout=30,
        )
        return tmp.name
    except Exception as e:
        logger.error("Failed to copy Radarr DB: %s", e)
        return None


def load_movie_records(db_path: str) -> dict[str, dict]:
    records_by_path: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT
                mf.Id AS movie_file_id,
                mf.MovieId AS movie_id,
                mf.RelativePath AS relative_path,
                m.Path AS movie_path,
                m.Tags AS tags,
                mm.Title AS title,
                mm.Year AS year
            FROM MovieFiles mf
            JOIN Movies m ON m.Id = mf.MovieId
            LEFT JOIN MovieMetadata mm ON mm.Id = m.MovieMetadataId
        """)
        for row in cursor.fetchall():
            full_path = str(Path(str(row["movie_path"])) / str(row["relative_path"]))
            records_by_path[full_path] = dict(row)
        conn.close()
    except Exception as e:
        logger.error("Failed to load Radarr records: %s", e)
    return records_by_path


async def delete_movie_file(url: str, api_key: str, file_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{url.rstrip('/')}/api/v3/moviefile/{file_id}?deleteFile=false",
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error("Failed to delete movie file %s: %s", file_id, e)
        return False


async def refresh_movie(url: str, api_key: str, movie_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json={"name": "RefreshMovie", "movieIds": [movie_id]},
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 201
    except Exception as e:
        logger.error("Failed to refresh movie %s: %s", movie_id, e)
        return False


async def search_movies(url: str, api_key: str, movie_ids: list[int]) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json={"name": "MoviesSearch", "movieIds": movie_ids},
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 201
    except Exception as e:
        logger.error("Failed to search movies: %s", e)
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
        logger.error("Failed to fetch Radarr tags: %s", e)
    return []
