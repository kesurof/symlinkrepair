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


def load_records(db_path: str, query: str) -> dict[str, dict]:
    records_by_path: dict[str, dict] = {}
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        for row in cursor.fetchall():
            full_path = row.get("full_path") or str(
                Path(str(row.get("base_path", ""))) / str(row.get("relative_path", ""))
            )
            records_by_path[full_path] = dict(row)
        conn.close()
    except Exception as e:
        logger.error("Failed to load records: %s", e)
    finally:
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception:
            pass
    return records_by_path


async def delete_file(url: str, api_key: str, endpoint: str, file_id: int) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{url.rstrip('/')}/api/v3/{endpoint}/{file_id}",
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error("Failed to delete %s %s: %s", endpoint, file_id, e)
        return False


async def send_command(url: str, api_key: str, command: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/api/v3/command",
                json=command,
                headers={"X-Api-Key": api_key},
            )
            return resp.status_code == 201
    except Exception as e:
        logger.error("Failed to send command %s: %s", command.get("name"), e)
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
        logger.error("Failed to fetch tags: %s", e)
    return []
