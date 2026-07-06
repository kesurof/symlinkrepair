import sqlite3
import tempfile
from pathlib import Path


def _create_sonarr_db(path: str):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE Series (
            Id INTEGER PRIMARY KEY, Title TEXT, Path TEXT, Tags TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE EpisodeFiles (
            Id INTEGER PRIMARY KEY, SeriesId INTEGER,
            RelativePath TEXT, SeasonNumber INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO Series (Id, Title, Path, Tags)"
        " VALUES (1, 'Test Series', '/series/Test', '[1,2]')"
    )
    conn.execute(
        "INSERT INTO EpisodeFiles (Id, SeriesId, RelativePath, SeasonNumber)"
        " VALUES (10, 1, 'S01/ep1.mkv', 1)"
    )
    conn.execute(
        "INSERT INTO EpisodeFiles (Id, SeriesId, RelativePath, SeasonNumber)"
        " VALUES (11, 1, 'S01/ep2.mkv', 1)"
    )
    conn.commit()
    conn.close()


def test_load_sonarr_records():
    from app.services.sonarr import load_episode_records

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_sonarr_db(db_path)
        records = load_episode_records(db_path)
        assert len(records) == 2, f"Expected 2 records, got {len(records)}"
        for fp, rec in records.items():
            assert rec["episode_file_id"] in (10, 11)
            assert rec["series_id"] == 1
            assert rec["title"] == "Test Series"
            assert rec.get("season") == 1
            assert "/series/Test/" in fp
    finally:
        Path(db_path).unlink(missing_ok=True)


def _create_radarr_db(path: str):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE MovieFiles (
            Id INTEGER PRIMARY KEY, MovieId INTEGER, RelativePath TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE Movies (
            Id INTEGER PRIMARY KEY, Path TEXT, Tags TEXT, MovieMetadataId INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE MovieMetadata (
            Id INTEGER PRIMARY KEY, Title TEXT, Year INTEGER
        )
    """)
    conn.execute("INSERT INTO MovieMetadata (Id, Title, Year) VALUES (1, 'Test Movie', 2024)")
    conn.execute(
        "INSERT INTO Movies (Id, Path, Tags, MovieMetadataId) VALUES (1, '/movies/Test', '[]', 1)"
    )
    conn.execute("INSERT INTO MovieFiles (Id, MovieId, RelativePath) VALUES (10, 1, 'test.mkv')")
    conn.commit()
    conn.close()


def test_load_radarr_records():
    from app.services.radarr import load_movie_records

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _create_radarr_db(db_path)
        records = load_movie_records(db_path)
        assert len(records) == 1, f"Expected 1 record, got {len(records)}"
        for fp, rec in records.items():
            assert rec["movie_file_id"] == 10
            assert rec["movie_id"] == 1
            assert rec["title"] == "Test Movie"
    finally:
        Path(db_path).unlink(missing_ok=True)
