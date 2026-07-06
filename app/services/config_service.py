import json
import logging
from pathlib import Path

from app.config import settings
from app.models.config import AppConfig

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(settings.data_dir) / "config.json"


def _load_raw() -> dict:
    if CONFIG_PATH.exists():
        raw = CONFIG_PATH.read_text()
        return json.loads(raw) if raw.strip() else {}
    return {}


def _save_raw(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def load_config() -> AppConfig:
    raw = _load_raw()
    logger.debug("Config loaded from %s", CONFIG_PATH)
    return AppConfig(**raw)


def save_config(cfg: AppConfig):
    stored = _load_raw()
    raw = cfg.model_dump()

    for section in ("radarr", "sonarr"):
        val = raw.get(section, {}).get("api_key", "")
        if val and ("..." in val or val == "********"):
            raw[section]["api_key"] = stored.get(section, {}).get("api_key", "")

    webhook = raw.get("discord", {}).get("webhook", "")
    if webhook and ("..." in webhook or webhook == "********"):
        raw["discord"]["webhook"] = stored.get("discord", {}).get("webhook", "")

    _save_raw(raw)
    logger.info("Config saved to %s", CONFIG_PATH)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return value[:4] + "..." + value[-4:]


def public_config() -> dict:
    raw = _load_raw()
    full = AppConfig(**raw)
    cfg = full.model_dump()
    radarr = cfg.get("radarr", {})
    sonarr = cfg.get("sonarr", {})
    discord = cfg.get("discord", {})
    if radarr.get("api_key"):
        radarr["api_key"] = mask_secret(radarr["api_key"])
    if sonarr.get("api_key"):
        sonarr["api_key"] = mask_secret(sonarr["api_key"])
    if discord.get("webhook"):
        discord["webhook"] = mask_secret(discord["webhook"])
    return cfg


def browse_directory(path_str: str, allowed_roots: list[str]) -> dict | None:
    path = Path(path_str).resolve()
    allowed = [Path(r).resolve() for r in allowed_roots]

    if not any(str(path).startswith(str(a)) for a in allowed):
        return None

    if not path.is_dir():
        return None

    try:
        directories = sorted(
            [
                {
                    "name": p.name,
                    "path": str(p.resolve()),
                    "is_symlink": p.is_symlink(),
                }
                for p in path.iterdir()
                if p.is_dir()
            ],
            key=lambda x: x["name"].lower(),
        )
    except PermissionError:
        directories = []

    parent = str(path.parent) if path.parent != path else ""
    can_go_up = bool(parent) and any(str(parent).startswith(str(a)) for a in allowed)

    return {
        "current": str(path),
        "parent": parent,
        "directories": directories,
        "can_go_up": can_go_up,
    }


async def _test_connection(source: str, url: str, api_key: str) -> dict:
    if not url or not api_key:
        return {"ok": False, "error": "URL ou clé API manquante"}
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/api/v3/system/status",
                headers={"X-Api-Key": api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                version = data.get("version", "?")
                logger.info("%s connection test: ok=True version=%s", source, version)
                return {"ok": True, "version": version}
            logger.warning("%s connection test: ok=False http=%d", source, resp.status_code)
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.warning("%s connection test: ok=False error=%s", source, e)
        return {"ok": False, "error": str(e)}


async def test_radarr_connection(url: str, api_key: str) -> dict:
    return await _test_connection("Radarr", url, api_key)


async def test_sonarr_connection(url: str, api_key: str) -> dict:
    return await _test_connection("Sonarr", url, api_key)
