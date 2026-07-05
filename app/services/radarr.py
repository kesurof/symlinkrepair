import logging

from app.services.arr_base import (
    copy_database,
    delete_file,
    load_records,
    send_command,
)
from app.services.arr_base import (
    fetch_tags as _fetch_tags,
)

logger = logging.getLogger(__name__)

RADARR_DB = "radarr.db"

RADARR_QUERY = """
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
"""


def copy_database_from_container(container: str) -> str | None:
    return copy_database(container, RADARR_DB)


def load_movie_records(db_path: str) -> dict[str, dict]:
    return load_records(db_path, RADARR_QUERY)


async def delete_movie_file(url: str, api_key: str, file_id: int) -> bool:
    return await delete_file(url, api_key, "moviefile", file_id)


async def refresh_movie(url: str, api_key: str, movie_id: int) -> bool:
    return await send_command(url, api_key, {"name": "RefreshMovie", "movieIds": [movie_id]})


async def search_movies(url: str, api_key: str, movie_ids: list[int]) -> bool:
    return await send_command(url, api_key, {"name": "MoviesSearch", "movieIds": movie_ids})


async def fetch_tags(url: str, api_key: str) -> list[dict]:
    return await _fetch_tags(url, api_key)
