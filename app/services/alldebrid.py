from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.alldebrid.com/v4.1"
MEDIA_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts", ".wmv", ".flv", ".webm", ".iso",
}
MAGNET_NAME_FIELDS = ("filename", "name", "originalName", "original_name", "displayName", "title")
FILE_NAME_KEYS = ("filename", "name", "path", "file", "basename", "displayName", "title")
DATE_FIELDS = (
    "created_at", "createdAt", "creationDate", "date",
    "uploadDate", "uploaded", "added", "added_at", "updated_at",
)
HASH_RE = re.compile(r"^[a-fA-F0-9]{32,64}$")


def strip_media_ext(name: str) -> str:
    p = Path(name)
    suffix = p.suffix.lower()
    if suffix in MEDIA_EXTENSIONS:
        return str(p.with_suffix(""))
    return name


def strict_key(name: str) -> str:
    if not name:
        return ""
    n = str(name).strip()
    n = Path(n.replace("\\", "/")).name
    n = strip_media_ext(n)
    n = n.lower()
    n = re.sub(r"[._\-\[\](){}!]+", " ", n)
    n = re.sub(r"[^a-z0-9àâäçéèêëîïôöùûüÿñæœ]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def candidate_variants(value: str) -> Set[str]:
    variants: Set[str] = set()
    if not value or not isinstance(value, str):
        return variants
    raw = value.strip()
    if not raw or raw.startswith(("http://", "https://")):
        return variants
    raw = raw.replace("\\", "/")
    variants.add(raw)
    variants.add(Path(raw).name)
    parts = [p for p in raw.split("/") if p]
    if parts:
        variants.add(parts[0])
        variants.add(parts[-1])
    for v in list(variants):
        variants.add(strip_media_ext(v))
        variants.add(Path(v).stem)
    return {v for v in variants if v}


def collect_strings_from_obj(obj: Any) -> Set[str]:
    values: Set[str] = set()
    def walk(value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, str(k))
        elif isinstance(value, list):
            for item in value:
                walk(item, key_hint)
        elif isinstance(value, str):
            s = value.strip()
            if not s or s.startswith(("http://", "https://")):
                return
            is_media = Path(s).suffix.lower() in MEDIA_EXTENSIONS
            if key_hint in FILE_NAME_KEYS or is_media or "/" in s or "\\" in s:
                values.update(candidate_variants(s))
    walk(obj)
    return values


def parse_age_hours(obj: Dict[str, Any]) -> Optional[float]:
    now = datetime.now(timezone.utc)
    for key in DATE_FIELDS:
        value = obj.get(key)
        if value in (None, ""):
            continue
        dt: Optional[datetime] = None
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 10_000_000_000:
                ts /= 1000
            try:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                dt = None
        elif isinstance(value, str):
            raw = value.strip()
            if re.fullmatch(r"\d{10,13}", raw):
                ts = float(raw)
                if ts > 10_000_000_000:
                    ts /= 1000
                try:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                except Exception:
                    dt = None
            else:
                try:
                    if raw.endswith("Z"):
                        raw = raw[:-1] + "+00:00"
                    dt = datetime.fromisoformat(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                except Exception:
                    dt = None
        if dt is not None:
            return max(0.0, (now - dt).total_seconds() / 3600)
    return None


def magnet_id(magnet: Dict[str, Any]) -> str:
    return str(magnet.get("id") or magnet.get("magnetId") or magnet.get("magnet_id") or "")


def magnet_primary_name(magnet: Dict[str, Any]) -> str:
    for field_name in MAGNET_NAME_FIELDS:
        val = magnet.get(field_name)
        if isinstance(val, str) and val.strip():
            return val.strip()
    mid = magnet_id(magnet)
    return f"unknown-{mid}" if mid else "unknown"


def magnet_candidate_names(magnet: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for field_name in MAGNET_NAME_FIELDS:
        val = magnet.get(field_name)
        if isinstance(val, str):
            names.update(candidate_variants(val))
    names.update(collect_strings_from_obj(magnet.get("files", [])))
    names.update(collect_strings_from_obj(magnet.get("links", [])))
    names.update(candidate_variants(magnet_primary_name(magnet)))
    return {n for n in names if n}


def is_hash_name(name: str) -> bool:
    return bool(HASH_RE.fullmatch(Path(name).name.strip()))


class AllDebridAPI:
    BASE_URL = "https://api.alldebrid.com/v4.1"

    def __init__(
        self, api_key: str, rate_limit: float = 0.2,
        retry_attempts: int = 3, retry_backoff: float = 2.0,
    ):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self._http_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(45.0),
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return self._http_client

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                resp = await client.request(method, url, **kwargs)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    await asyncio.sleep(self.retry_backoff ** attempt)
                    continue
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            except (
                httpx.HTTPError, asyncio.TimeoutError,
                RuntimeError, json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break
                await asyncio.sleep(self.retry_backoff ** attempt)
        raise RuntimeError(f"API error after {self.retry_attempts} attempt(s): {last_error}")

    async def get_magnets(self) -> List[Dict[str, Any]]:
        response = await self.request("GET", "/magnet/status")
        if response.get("status") != "success":
            err = response.get("error") or {}
            raise RuntimeError(f"AllDebrid API error: {err.get('message', err)}")
        data = response.get("data") or {}
        magnets = data.get("magnets") or []
        if isinstance(magnets, dict):
            magnets = list(magnets.values())
        if not isinstance(magnets, list):
            raise RuntimeError("Unexpected API format: data.magnets is not a list")
        return [m for m in magnets if isinstance(m, dict)]

    async def delete_magnet(self, mid: str) -> bool:
        response = await self.request("POST", "/magnet/delete", data={"id": str(mid)})
        return response.get("status") == "success"

    async def __aenter__(self) -> "AllDebridAPI":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
