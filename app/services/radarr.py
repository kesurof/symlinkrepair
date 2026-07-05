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
        return tmp.name
    except Exception as e:
        logger.error("Failed to copy %s from %s: %s", db_name, container, e)
        if tmp and Path(tmp.name).exists():
            Path(tmp.name).unlink(missing_ok=True)
        return None


def copy_database_from_container(container: str) -> str | None:
    return copy_database(container, "radarr.db")


def load_movie_records(db_path: str) -> dict[str, dict]:
    records_by_path: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT
                mf.Id AS movie_file_id,
                mf.MovieId AS movie_id,
                (m.Path || '/' || mf.RelativePath) AS full_path,
                m.Tags AS tags,
                mm.Title AS title,
                mm.Year AS year
            FROM MovieFiles mf
            JOIN Movies m ON m.Id = mf.MovieId
            LEFT JOIN MovieMetadata mm ON mm.Id = m.MovieMetadataId
        """)
        for row in cursor.fetchall():
            d = dict(row)
            fp = d.get("full_path", "")
            if fp:
                records_by_path[fp] = d
        conn.close()
    except Exception as e:
        logger.error("Failed to load Radarr records: %s", e)
    finally:
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception:
            pass
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
