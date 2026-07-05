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

SONARR_DB = "sonarr.db"

SONARR_QUERY = """
    SELECT
        ef.Id AS episode_file_id,
        ef.SeriesId AS series_id,
        (s.Path || '/' || ef.RelativePath) AS full_path,
        e.SeasonNumber AS season,
        e.EpisodeNumber AS episode,
        s.Tags AS tags,
        sm.Title AS title
    FROM EpisodeFiles ef
    JOIN Episodes e ON e.EpisodeFileId = ef.Id
    JOIN Series s ON s.Id = ef.SeriesId
    LEFT JOIN SeriesMetadata sm ON sm.Id = s.SeriesMetadataId
"""


def copy_database_from_container(container: str) -> str | None:
    return copy_database(container, SONARR_DB)


def load_episode_records(db_path: str) -> dict[str, dict]:
    return load_records(db_path, SONARR_QUERY)


async def delete_episode_file(url: str, api_key: str, file_id: int) -> bool:
    return await delete_file(url, api_key, "episodefile", file_id)


async def rescan_series(url: str, api_key: str, series_id: int) -> bool:
    return await send_command(url, api_key, {"name": "RescanSeries", "seriesId": series_id})


async def search_season(url: str, api_key: str, series_id: int, season: int) -> bool:
    return await send_command(
        url, api_key, {"name": "SeasonSearch", "seriesId": series_id, "seasonNumber": season}
    )


async def fetch_tags(url: str, api_key: str) -> list[dict]:
    return await _fetch_tags(url, api_key)
