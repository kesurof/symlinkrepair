import logging
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
