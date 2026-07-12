#!/usr/bin/env python3
"""
Orphan Manager STRICT pour AllDebrid + Decypharr DFS
====================================================

Version stricte : pas de fuzzy matching, pas de score, pas de "match incertain".

Règle unique :
- un magnet est UTILISÉ si l'un de ses noms API correspond exactement à un nom
  extrait des symlinks médias, après normalisation stricte case/ponctuation/extension ;
- sinon il est ORPHELIN candidat, sauf protection âge minimum optionnelle.

Important :
- ne scanne jamais récursivement /mnt/decypharr/.../__all__ ;
- lit uniquement les symlinks sous medias_base ;
- compare avec l'API AllDebrid ;
- supprime uniquement via API avec --execute.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import logging.handlers
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import aiohttp
except ImportError:
    print("Module manquant: aiohttp. Installe avec: pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    import yaml
except ImportError:
    print("Module manquant: pyyaml. Installe avec: pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

MEDIA_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".m4v", ".ts", ".m2ts", ".wmv", ".flv", ".webm",
    ".iso",
}

MAGNET_NAME_FIELDS = (
    "filename", "name", "originalName", "original_name", "displayName", "title"
)

FILE_NAME_KEYS = (
    "filename", "name", "path", "file", "basename", "displayName", "title"
)

DATE_FIELDS = (
    "created_at", "createdAt", "creationDate", "date", "uploadDate", "uploaded", "added", "added_at", "updated_at"
)

HASH_RE = re.compile(r"^[a-fA-F0-9]{32,64}$")


@dataclass
class GlobalConfig:
    medias_base: Path
    log_dir: Path
    log_retention_days: int = 7
    cycle_count: int = 1
    cycle_interval: int = 60
    exclude_dirs: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    min_age_hours: int = 24
    json_logging: bool = True
    syslog_logging: bool = False

    def __post_init__(self) -> None:
        self.medias_base = Path(self.medias_base)
        self.log_dir = Path(self.log_dir)


@dataclass
class AllDebridInstance:
    name: str
    api_key: str
    mount_path: Path
    target_prefixes: List[Path]
    rate_limit: float = 0.2
    retry_attempts: int = 3
    retry_backoff: float = 2.0
    enabled: bool = True

    def __post_init__(self) -> None:
        self.mount_path = Path(self.mount_path)
        self.target_prefixes = [Path(p) for p in self.target_prefixes]
        if not self.target_prefixes:
            self.target_prefixes = [self.mount_path / "__all__", self.mount_path / "torrents", self.mount_path]
        self.target_prefixes = sorted(self.target_prefixes, key=lambda p: len(str(p)), reverse=True)


@dataclass
class SymlinkUsage:
    total_symlinks: int = 0
    matching_symlinks: int = 0
    used_raw_names: Set[str] = field(default_factory=set)
    used_strict_keys: Set[str] = field(default_factory=set)
    used_torrent_dirs: Set[str] = field(default_factory=set)
    used_file_names: Set[str] = field(default_factory=set)
    sample_targets: List[str] = field(default_factory=list)


@dataclass
class MagnetCandidate:
    instance_name: str
    magnet_id: str
    primary_name: str
    raw: Dict[str, Any]
    candidate_names: Set[str]
    candidate_keys: Set[str]
    age_hours: Optional[float]
    status: str
    match_name: str = ""
    match_key: str = ""


@dataclass
class ScanResult:
    instance_name: str
    total_symlinks: int
    matching_symlinks: int
    used_torrent_count: int
    used_key_count: int
    total_magnets: int
    used_count: int
    protected_recent_count: int
    orphan_count: int
    duration: float
    used: List[MagnetCandidate]
    protected_recent: List[MagnetCandidate]
    orphans: List[MagnetCandidate]


class JSONLogger:
    def __init__(self, path: Optional[Path], enabled: bool = True):
        self.path = path
        self.enabled = enabled and path is not None
        if self.enabled and self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **kwargs: Any) -> None:
        if not self.enabled or self.path is None:
            return
        entry = {"timestamp": datetime.now().isoformat(timespec="seconds"), "event": event, **kwargs}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def setup_logger(config: GlobalConfig, name: str = "orphan-manager-strict") -> Tuple[logging.Logger, JSONLogger]:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name.lower())
    log_path = config.log_dir / f"{safe}_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    if config.syslog_logging:
        try:
            sh = logging.handlers.SysLogHandler(address="/dev/log")
            sh.setFormatter(logging.Formatter(f"{safe}: %(message)s"))
            logger.addHandler(sh)
        except Exception:
            pass

    json_path = config.log_dir / f"{safe}_{datetime.now().strftime('%Y%m%d')}.jsonl"
    return logger, JSONLogger(json_path, enabled=config.json_logging)


def norm_path_string(path: Path | str) -> str:
    return os.path.normpath(str(path))


def is_under_path(path: str, prefix: str) -> bool:
    path_n = os.path.normpath(path)
    prefix_n = os.path.normpath(prefix)
    return path_n == prefix_n or path_n.startswith(prefix_n.rstrip("/") + "/")


def relative_parts_no_resolve(path: str, prefix: str) -> Tuple[str, ...]:
    path_n = os.path.normpath(path)
    prefix_n = os.path.normpath(prefix)
    if path_n == prefix_n:
        return tuple()
    rel = path_n[len(prefix_n.rstrip("/")) + 1:]
    return tuple(part for part in rel.split(os.sep) if part)


def strip_media_ext(name: str) -> str:
    p = Path(name)
    suffix = p.suffix.lower()
    if suffix in MEDIA_EXTENSIONS:
        return str(p.with_suffix(""))
    return name


def strict_key(name: str) -> str:
    """
    Clé stricte déterministe.

    Autorisé : ignorer casse, accents simples non traités, ponctuation/séparateurs,
    extension média finale, espaces multiples.

    Interdit : aucun token partagé, aucune similarité, aucun startswith global.
    """
    if not name:
        return ""
    n = str(name).strip()
    n = os.path.basename(n.replace("\\", "/"))
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
    variants.add(os.path.basename(raw))

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
            if key_hint in FILE_NAME_KEYS or Path(s).suffix.lower() in MEDIA_EXTENSIONS or "/" in s or "\\" in s:
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
    base = os.path.basename(name).strip()
    return bool(HASH_RE.fullmatch(base))


class AllDebridAPI:
    BASE_URL = "https://api.alldebrid.com/v4.1"
    _open_sessions: Set[aiohttp.ClientSession] = set()

    def __init__(self, api_key: str, rate_limit: float = 0.2, retry_attempts: int = 3, retry_backoff: float = 2.0):
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "AllDebridAPI":
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        AllDebridAPI._open_sessions.add(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session:
            await self.session.close()
            AllDebridAPI._open_sessions.discard(self.session)

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("Session API non initialisée")
        url = f"{self.BASE_URL}{endpoint}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                async with self.session.request(method, url, **kwargs) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        return json.loads(text)
                    if resp.status == 429:
                        await asyncio.sleep(self.retry_backoff ** attempt)
                        continue
                    raise RuntimeError(f"HTTP {resp.status}: {text[:300]}")
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break
                await asyncio.sleep(self.retry_backoff ** attempt)
        raise RuntimeError(f"Erreur API après {self.retry_attempts} tentative(s): {last_error}")

    async def get_magnets(self) -> List[Dict[str, Any]]:
        response = await self.request("GET", "/magnet/status")
        if response.get("status") != "success":
            err = response.get("error") or {}
            raise RuntimeError(f"Erreur API AllDebrid: {err.get('message', err)}")
        data = response.get("data") or {}
        magnets = data.get("magnets") or []
        if isinstance(magnets, dict):
            magnets = list(magnets.values())
        if not isinstance(magnets, list):
            raise RuntimeError("Format API inattendu: data.magnets n'est pas une liste")
        return [m for m in magnets if isinstance(m, dict)]

    async def delete_magnet(self, mid: str) -> bool:
        form = aiohttp.FormData()
        form.add_field("id", str(mid))
        response = await self.request("POST", "/magnet/delete", data=form)
        return response.get("status") == "success"

    @classmethod
    async def close_all_sessions(cls) -> None:
        for session in list(cls._open_sessions):
            try:
                await session.close()
            except Exception:
                pass
            cls._open_sessions.discard(session)


class OrphanDetector:
    def __init__(self, config: GlobalConfig, instance: AllDebridInstance, logger: logging.Logger, json_logger: JSONLogger):
        self.config = config
        self.instance = instance
        self.logger = logger
        self.json_logger = json_logger

    def build_symlink_dirs(self) -> List[Path]:
        base = self.config.medias_base
        if not base.exists() or not base.is_dir():
            raise RuntimeError(f"medias_base introuvable ou non dossier: {base}")
        dirs: List[Path] = []
        if self.config.include_dirs:
            for name in self.config.include_dirs:
                p = base / name
                if p.exists() and p.is_dir():
                    dirs.append(p)
                else:
                    self.logger.warning(f"include_dir introuvable ignoré: {p}")
        else:
            for p in sorted(base.iterdir(), key=lambda x: x.name.lower()):
                if not p.is_dir():
                    continue
                if p.name in self.config.exclude_dirs:
                    continue
                dirs.append(p)
        return dirs

    def match_target_prefix(self, target: str) -> Optional[Tuple[Path, Tuple[str, ...]]]:
        for prefix in self.instance.target_prefixes:
            ps = norm_path_string(prefix)
            if is_under_path(target, ps):
                return prefix, relative_parts_no_resolve(target, ps)
        return None

    def add_used_name(self, usage: SymlinkUsage, name: str) -> None:
        if not name:
            return
        for variant in candidate_variants(name):
            key = strict_key(variant)
            if key:
                usage.used_raw_names.add(variant)
                usage.used_strict_keys.add(key)

    def scan_symlinks(self, dirs: List[Path]) -> SymlinkUsage:
        usage = SymlinkUsage()
        for root_dir in dirs:
            self.logger.debug(f"Scan symlinks: {root_dir}")
            for root, dirnames, filenames in os.walk(root_dir, followlinks=False):
                for name in list(dirnames) + list(filenames):
                    full_path = os.path.join(root, name)
                    try:
                        if not os.path.islink(full_path):
                            continue
                        usage.total_symlinks += 1
                        raw_target = os.readlink(full_path)
                        target = os.path.normpath(raw_target if os.path.isabs(raw_target) else os.path.join(root, raw_target))
                        matched = self.match_target_prefix(target)
                        if not matched:
                            continue
                        _prefix, parts = matched
                        if not parts:
                            continue
                        usage.matching_symlinks += 1
                        torrent_dir = parts[0]
                        file_name = parts[-1]
                        usage.used_torrent_dirs.add(torrent_dir)
                        usage.used_file_names.add(file_name)
                        self.add_used_name(usage, torrent_dir)
                        self.add_used_name(usage, file_name)
                        self.add_used_name(usage, Path(file_name).stem)
                        if len(usage.sample_targets) < 20:
                            usage.sample_targets.append(target)
                    except OSError as exc:
                        self.logger.debug(f"Symlink ignoré {full_path}: {exc}")
        return usage

    def classify_magnet(self, magnet: Dict[str, Any], usage: SymlinkUsage) -> MagnetCandidate:
        mid = magnet_id(magnet)
        primary = magnet_primary_name(magnet)
        names = magnet_candidate_names(magnet)
        keys = {strict_key(n) for n in names}
        keys = {k for k in keys if k}
        age = parse_age_hours(magnet)

        matched_key = ""
        matched_name = ""
        for key in sorted(keys):
            if key in usage.used_strict_keys:
                matched_key = key
                # retrouver un nom lisible candidat correspondant
                matched_name = next((n for n in names if strict_key(n) == key), "")
                break

        if matched_key:
            status = "used"
        elif age is not None and age < self.config.min_age_hours:
            status = "protected_recent"
        else:
            status = "orphan"

        return MagnetCandidate(
            instance_name=self.instance.name,
            magnet_id=mid,
            primary_name=primary,
            raw=magnet,
            candidate_names=names,
            candidate_keys=keys,
            age_hours=age,
            status=status,
            match_name=matched_name,
            match_key=matched_key,
        )

    async def find_orphans(self) -> ScanResult:
        start = time.time()
        self.json_logger.log("scan_started", instance=self.instance.name)
        dirs = self.build_symlink_dirs()
        self.logger.info(f"Dossiers médias à scanner: {len(dirs)}")
        self.logger.info("Scan symlinks médias...")
        usage = self.scan_symlinks(dirs)
        self.logger.info(f"✓ {usage.matching_symlinks} symlinks vers cette instance / {usage.total_symlinks} symlinks totaux")
        self.logger.info(f"✓ {len(usage.used_torrent_dirs)} dossiers torrents utilisés")
        self.logger.info(f"✓ {len(usage.used_strict_keys)} clés strictes utilisées")

        self.logger.info("Lecture AllDebrid API...")
        async with AllDebridAPI(self.instance.api_key, self.instance.rate_limit, self.instance.retry_attempts, self.instance.retry_backoff) as api:
            magnets = await api.get_magnets()
        self.logger.info(f"✓ {len(magnets)} magnets AllDebrid")

        self.logger.info("Comparaison stricte magnets ↔ symlinks...")
        classified = [self.classify_magnet(m, usage) for m in magnets]
        used = [c for c in classified if c.status == "used"]
        protected_recent = [c for c in classified if c.status == "protected_recent"]
        orphans = [c for c in classified if c.status == "orphan"]

        result = ScanResult(
            instance_name=self.instance.name,
            total_symlinks=usage.total_symlinks,
            matching_symlinks=usage.matching_symlinks,
            used_torrent_count=len(usage.used_torrent_dirs),
            used_key_count=len(usage.used_strict_keys),
            total_magnets=len(magnets),
            used_count=len(used),
            protected_recent_count=len(protected_recent),
            orphan_count=len(orphans),
            duration=time.time() - start,
            used=sorted(used, key=lambda c: c.primary_name.lower()),
            protected_recent=sorted(protected_recent, key=lambda c: c.primary_name.lower()),
            orphans=sorted(orphans, key=lambda c: c.primary_name.lower()),
        )
        self.json_logger.log(
            "scan_completed",
            instance=self.instance.name,
            total_symlinks=result.total_symlinks,
            matching_symlinks=result.matching_symlinks,
            used_torrent_count=result.used_torrent_count,
            used_key_count=result.used_key_count,
            total_magnets=result.total_magnets,
            used=result.used_count,
            protected_recent=result.protected_recent_count,
            orphans=result.orphan_count,
            duration=round(result.duration, 2),
        )
        return result


class OrphanManager:
    def __init__(self, config_path: Path, args: argparse.Namespace):
        self.config_path = config_path
        self.args = args
        self.raw_config = self.load_yaml(config_path)
        self.global_config = self.parse_global_config(self.raw_config, args)
        self.instances = self.parse_instances(self.raw_config)
        self.logger, self.json_logger = setup_logger(self.global_config)
        self.console = Console(stderr=True) if RICH_AVAILABLE and sys.stderr.isatty() else None
        self.cleanup_old_logs()

    @staticmethod
    def load_yaml(path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise RuntimeError(f"Fichier config introuvable: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise RuntimeError("Config YAML invalide")
        return data

    @staticmethod
    def parse_global_config(data: Dict[str, Any], args: argparse.Namespace) -> GlobalConfig:
        g = data.get("global") or {}
        logging_cfg = data.get("logging") or {}
        return GlobalConfig(
            medias_base=Path(g.get("medias_base", "/home/kesurof/Medias")),
            log_dir=Path(g.get("log_dir", "./logs")),
            log_retention_days=int(g.get("log_retention_days", 7)),
            cycle_count=int(g.get("cycle_count", 1)),
            cycle_interval=int(g.get("cycle_interval", 60)),
            exclude_dirs=list(g.get("exclude_dirs") or []),
            include_dirs=list(g.get("include_dirs") or []),
            min_age_hours=int(args.min_age_hours if args.min_age_hours is not None else g.get("min_age_hours", 24)),
            json_logging=bool(logging_cfg.get("json_logging", True)),
            syslog_logging=bool(logging_cfg.get("syslog_logging", False)),
        )

    @staticmethod
    def parse_instances(data: Dict[str, Any]) -> List[AllDebridInstance]:
        instances = []
        for raw in data.get("instances") or []:
            if not raw:
                continue
            mount_path = Path(raw["mount_path"])
            prefixes = raw.get("target_prefixes")
            if prefixes:
                target_prefixes = [Path(p) for p in prefixes]
            else:
                target_prefixes = [mount_path / "__all__", mount_path / "torrents", mount_path]
            instances.append(AllDebridInstance(
                name=str(raw["name"]),
                enabled=bool(raw.get("enabled", True)),
                api_key=str(raw["api_key"]),
                mount_path=mount_path,
                target_prefixes=target_prefixes,
                rate_limit=float(raw.get("rate_limit", 0.2)),
                retry_attempts=int(raw.get("retry_attempts", 3)),
                retry_backoff=float(raw.get("retry_backoff", 2.0)),
            ))
        return instances

    def cleanup_old_logs(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.global_config.log_retention_days)
        for pattern in ("*.log", "*.jsonl"):
            for path in self.global_config.log_dir.glob(pattern):
                try:
                    if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                        path.unlink()
                except OSError:
                    pass

    def selected_instances(self, target: Optional[str]) -> List[AllDebridInstance]:
        selected = [i for i in self.instances if i.enabled]
        if target:
            tl = target.lower()
            selected = [i for i in selected if i.name.lower() == tl]
        if not selected:
            raise RuntimeError("Aucune instance active trouvée")
        return selected

    def print_header(self) -> None:
        title = "Orphan Manager STRICT — AllDebrid / Decypharr DFS"
        if self.console:
            self.console.print(Panel.fit(title, box=box.DOUBLE, style="cyan"))
        else:
            self.logger.info(title)

    def print_result(self, result: ScanResult) -> None:
        if self.console:
            table = Table(title=f"Résultat strict — {result.instance_name}", box=box.SIMPLE)
            table.add_column("Indicateur")
            table.add_column("Valeur", justify="right")
            table.add_row("Symlinks totaux scannés", str(result.total_symlinks))
            table.add_row("Symlinks vers instance", str(result.matching_symlinks))
            table.add_row("Dossiers torrents utilisés", str(result.used_torrent_count))
            table.add_row("Clés strictes utilisées", str(result.used_key_count))
            table.add_row("Magnets AllDebrid", str(result.total_magnets))
            table.add_row("Match exact", str(result.used_count))
            table.add_row("Protégés récents", str(result.protected_recent_count))
            table.add_row("Orphelins candidats", str(result.orphan_count))
            table.add_row("Durée", f"{result.duration:.1f}s")
            self.console.print(table)
        else:
            self.logger.info(
                f"Résultat strict {result.instance_name}: magnets={result.total_magnets}, match_exact={result.used_count}, "
                f"protégés_récents={result.protected_recent_count}, orphelins={result.orphan_count}, durée={result.duration:.1f}s"
            )
        if self.args.details:
            self.print_candidates("ORPHELINS CANDIDATS À SUPPRIMER", result.orphans)
        if self.args.show_used:
            self.print_candidates("MATCH EXACT — UTILISÉS", result.used)
        if self.args.show_protected:
            self.print_candidates("PROTÉGÉS — RÉCENTS", result.protected_recent)

    def print_candidates(self, title: str, candidates: List[MagnetCandidate], max_items: int = 300) -> None:
        if not candidates:
            return
        print(f"\n{title} ({len(candidates)})", file=sys.stderr)
        print("-" * min(90, len(title) + 10), file=sys.stderr)
        for idx, c in enumerate(candidates[:max_items], 1):
            age = "inconnu" if c.age_hours is None else f"{c.age_hours:.1f}h"
            flag = " HASH" if is_hash_name(c.primary_name) else ""
            print(f"{idx:>4}. ID={c.magnet_id} | age={age}{flag} | {c.primary_name}", file=sys.stderr)
            if c.match_key:
                print(f"      match exact: {c.match_name} | clé: {c.match_key}", file=sys.stderr)
        if len(candidates) > max_items:
            print(f"... et {len(candidates) - max_items} autres", file=sys.stderr)

    def export_json(self, results: List[ScanResult], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        def cand(c: MagnetCandidate) -> Dict[str, Any]:
            return {
                "instance": c.instance_name,
                "magnet_id": c.magnet_id,
                "primary_name": c.primary_name,
                "status": c.status,
                "age_hours": c.age_hours,
                "match_name": c.match_name,
                "match_key": c.match_key,
                "candidate_names": sorted(c.candidate_names),
                "candidate_keys": sorted(c.candidate_keys),
            }
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "strict_exact_key",
            "config": str(self.config_path),
            "results": [
                {
                    "instance": r.instance_name,
                    "summary": {
                        "total_symlinks": r.total_symlinks,
                        "matching_symlinks": r.matching_symlinks,
                        "used_torrent_count": r.used_torrent_count,
                        "used_key_count": r.used_key_count,
                        "total_magnets": r.total_magnets,
                        "used_count": r.used_count,
                        "protected_recent_count": r.protected_recent_count,
                        "orphan_count": r.orphan_count,
                        "duration": r.duration,
                    },
                    "orphans": [cand(c) for c in r.orphans],
                    "protected_recent": [cand(c) for c in r.protected_recent],
                    "used": [cand(c) for c in r.used],
                }
                for r in results
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.logger.info(f"Rapport JSON exporté: {path}")

    def export_csv(self, results: List[ScanResult], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "instance", "status", "magnet_id", "primary_name", "age_hours", "match_name", "match_key", "is_hash",
            ])
            writer.writeheader()
            for r in results:
                for c in r.orphans + r.protected_recent + r.used:
                    writer.writerow({
                        "instance": c.instance_name,
                        "status": c.status,
                        "magnet_id": c.magnet_id,
                        "primary_name": c.primary_name,
                        "age_hours": "" if c.age_hours is None else f"{c.age_hours:.2f}",
                        "match_name": c.match_name,
                        "match_key": c.match_key,
                        "is_hash": "yes" if is_hash_name(c.primary_name) else "no",
                    })
        self.logger.info(f"Rapport CSV exporté: {path}")

    async def process_instance(self, instance: AllDebridInstance) -> ScanResult:
        logger, json_logger = setup_logger(self.global_config, f"orphan-strict-{instance.name}")
        logger.info("=" * 60)
        logger.info(f"Instance: {instance.name}")
        logger.info(f"Mount path déclaré: {instance.mount_path}")
        logger.info("Préfixes symlinks acceptés:")
        for p in instance.target_prefixes:
            logger.info(f"  - {p}")
        detector = OrphanDetector(self.global_config, instance, logger, json_logger)
        return await detector.find_orphans()

    async def delete_orphans(self, instance: AllDebridInstance, candidates: List[MagnetCandidate]) -> Dict[str, int]:
        stats = {"success": 0, "errors": 0, "skipped_no_id": 0}
        logger, json_logger = setup_logger(self.global_config, f"delete-strict-{instance.name}")
        async with AllDebridAPI(instance.api_key, instance.rate_limit, instance.retry_attempts, instance.retry_backoff) as api:
            total = len(candidates)
            for idx, c in enumerate(candidates, 1):
                if not c.magnet_id:
                    logger.warning(f"[{idx}/{total}] Pas d'ID, ignoré: {c.primary_name}")
                    stats["skipped_no_id"] += 1
                    continue
                logger.info(f"[{idx}/{total}] Suppression ID={c.magnet_id} | {c.primary_name[:100]}")
                ok = await api.delete_magnet(c.magnet_id)
                if ok:
                    stats["success"] += 1
                    json_logger.log("magnet_deleted", instance=instance.name, magnet_id=c.magnet_id, name=c.primary_name)
                else:
                    stats["errors"] += 1
                    json_logger.log("magnet_delete_error", instance=instance.name, magnet_id=c.magnet_id, name=c.primary_name)
                await asyncio.sleep(instance.rate_limit)
        return stats

    async def run_debug_symlinks(self) -> int:
        for instance in self.selected_instances(self.args.instance):
            logger, json_logger = setup_logger(self.global_config, f"debug-strict-{instance.name}")
            detector = OrphanDetector(self.global_config, instance, logger, json_logger)
            usage = detector.scan_symlinks(detector.build_symlink_dirs())
            print(f"\nInstance: {instance.name}")
            print(f"Symlinks totaux: {usage.total_symlinks}")
            print(f"Symlinks vers instance: {usage.matching_symlinks}")
            print(f"Dossiers torrents utilisés: {len(usage.used_torrent_dirs)}")
            print(f"Clés strictes utilisées: {len(usage.used_strict_keys)}")
            print("\nExemples de cibles:")
            for target in usage.sample_targets:
                print(f"  - {target}")
        return 0

    async def run_test_path(self, path_value: str) -> int:
        target = path_value
        if os.path.islink(path_value):
            target = os.readlink(path_value)
            if not os.path.isabs(target):
                target = os.path.normpath(os.path.join(os.path.dirname(path_value), target))
        print(f"Chemin testé: {path_value}")
        print(f"Cible: {target}")
        found = False
        for instance in self.instances:
            detector = OrphanDetector(self.global_config, instance, self.logger, self.json_logger)
            matched = detector.match_target_prefix(target)
            if matched:
                prefix, parts = matched
                found = True
                print(f"\nInstance matchée: {instance.name}")
                print(f"Préfixe: {prefix}")
                print(f"Torrent extrait: {parts[0] if parts else '(aucun)'}")
                print(f"Fichier extrait: {parts[-1] if parts else '(aucun)'}")
                print(f"Clé stricte torrent: {strict_key(parts[0]) if parts else ''}")
                print(f"Clé stricte fichier: {strict_key(parts[-1]) if parts else ''}")
        return 0 if found else 2

    async def run_debug_list(self) -> int:
        for instance in self.selected_instances(self.args.instance):
            print(f"\nInstance: {instance.name}")
            async with AllDebridAPI(instance.api_key, instance.rate_limit, instance.retry_attempts, instance.retry_backoff) as api:
                magnets = await api.get_magnets()
            for m in magnets:
                print(f"ID={magnet_id(m)} | {magnet_primary_name(m)}")
        return 0

    async def run(self) -> int:
        self.print_header()
        if self.args.debug_symlinks:
            return await self.run_debug_symlinks()
        if self.args.debug_list:
            return await self.run_debug_list()
        if self.args.test_path:
            return await self.run_test_path(self.args.test_path)

        self.logger.info(f"Mode: {'SUPPRESSION' if self.args.execute else 'DRY-RUN'}")
        self.logger.info(f"Matching: STRICT exact key uniquement")
        self.logger.info(f"Protection âge minimum: {self.global_config.min_age_hours}h")

        results: List[ScanResult] = []
        selected = self.selected_instances(self.args.instance)
        for instance in selected:
            result = await self.process_instance(instance)
            results.append(result)
            self.print_result(result)

        if self.args.export_json:
            self.export_json(results, Path(self.args.export_json))
        if self.args.export_csv:
            self.export_csv(results, Path(self.args.export_csv))

        total_orphans = sum(r.orphan_count for r in results)
        if total_orphans == 0:
            self.logger.info("Aucun orphelin candidat détecté.")
            return 0

        self.logger.warning(f"Orphelins candidats détectés: {total_orphans}")
        if not self.args.execute:
            self.logger.warning("Dry-run uniquement : aucune suppression effectuée.")
            return 2

        if not self.args.yes:
            print(f"\nConfirmer la suppression de {total_orphans} magnets AllDebrid ? [y/N]: ", end="", file=sys.stderr)
            answer = input().strip().lower()
            if answer not in {"y", "yes", "o", "oui"}:
                self.logger.info("Suppression annulée.")
                return 2

        deleted_any = False
        for result in results:
            instance = next(i for i in selected if i.name == result.instance_name)
            if not result.orphans:
                continue
            stats = await self.delete_orphans(instance, result.orphans)
            deleted_any = deleted_any or stats["success"] > 0
            self.logger.info(f"Résumé suppression {instance.name}: {stats}")
        return 0 if deleted_any else 1



def build_args(
    *,
    config: Path,
    instance: Optional[str] = None,
    execute: bool = False,
    yes: bool = False,
    details: bool = False,
    show_used: bool = False,
    show_protected: bool = False,
    export_json: Optional[str] = None,
    export_csv: Optional[str] = None,
    min_age_hours: Optional[int] = None,
    debug_symlinks: bool = False,
    debug_list: bool = False,
    test_path: Optional[str] = None,
    menu: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        config=config,
        instance=instance,
        execute=execute,
        yes=yes,
        details=details,
        show_used=show_used,
        show_protected=show_protected,
        export_json=export_json,
        export_csv=export_csv,
        min_age_hours=min_age_hours,
        debug_symlinks=debug_symlinks,
        debug_list=debug_list,
        test_path=test_path,
        menu=menu,
    )


async def run_once(args: argparse.Namespace) -> int:
    manager = OrphanManager(args.config, args)
    return await manager.run()


def load_instances_for_menu(config_path: Path) -> List[str]:
    data = OrphanManager.load_yaml(config_path)
    names: List[str] = []
    for raw in data.get("instances") or []:
        if raw and raw.get("enabled", True):
            names.append(str(raw.get("name", "")).strip())
    return [n for n in names if n]


def menu_print(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def menu_input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def choose_instance(config_path: Path) -> Optional[str]:
    instances = load_instances_for_menu(config_path)
    if not instances:
        print("Aucune instance active dans config.yaml")
        return None

    print("\nInstances disponibles:")
    for idx, name in enumerate(instances, 1):
        print(f"  [{idx}] {name}")
    print("  [0] Retour")

    choice = menu_input("Choisir une instance: ")
    if choice in {"0", ""}:
        return None

    try:
        index = int(choice)
        if 1 <= index <= len(instances):
            return instances[index - 1]
    except ValueError:
        pass

    # Permet aussi de taper le nom exact
    for name in instances:
        if choice.lower() == name.lower():
            return name

    print("Choix invalide.")
    return None


def reports_path(prefix: str, ext: str = "csv") -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", prefix.lower()).strip("_")
    return str(Path("reports") / f"{safe}_{stamp}.{ext}")


async def run_menu(config_path: Path) -> int:
    """
    Menu interactif simple.

    Important:
    - ce menu appelle le même moteur strict que la CLI ;
    - aucune activation manuelle du venv n'est nécessaire si tu passes par le lanceur shell ;
    - les suppressions demandent confirmation sauf choix explicite --yes en CLI.
    """
    while True:
        menu_print("Orphan Manager STRICT — Menu")
        print("  [1] Scanner une instance avec détails")
        print("  [2] Scanner toutes les instances")
        print("  [3] Supprimer les orphelins d'une instance")
        print("  [4] Supprimer les orphelins de toutes les instances")
        print("  [5] Export CSV d'une instance")
        print("  [6] Debug symlinks d'une instance")
        print("  [7] Lister magnets AllDebrid d'une instance")
        print("  [8] Tester un symlink ou une cible")
        print("  [9] Afficher les instances actives")
        print("  [0] Quitter")

        choice = menu_input("\nChoix: ")

        try:
            if choice == "1":
                inst = choose_instance(config_path)
                if inst:
                    await run_once(build_args(config=config_path, instance=inst, details=True))

            elif choice == "2":
                await run_once(build_args(config=config_path, details=False))

            elif choice == "3":
                inst = choose_instance(config_path)
                if inst:
                    await run_once(build_args(config=config_path, instance=inst, execute=True, details=True))

            elif choice == "4":
                await run_once(build_args(config=config_path, execute=True, details=True))

            elif choice == "5":
                inst = choose_instance(config_path)
                if inst:
                    path = reports_path(inst, "csv")
                    await run_once(build_args(config=config_path, instance=inst, details=True, export_csv=path))

            elif choice == "6":
                inst = choose_instance(config_path)
                if inst:
                    await run_once(build_args(config=config_path, instance=inst, debug_symlinks=True))

            elif choice == "7":
                inst = choose_instance(config_path)
                if inst:
                    await run_once(build_args(config=config_path, instance=inst, debug_list=True))

            elif choice == "8":
                path = menu_input("Chemin du symlink ou de la cible: ")
                if path:
                    await run_once(build_args(config=config_path, test_path=path))

            elif choice == "9":
                instances = load_instances_for_menu(config_path)
                print("\nInstances actives:")
                for name in instances:
                    print(f"  - {name}")

            elif choice == "0" or choice.lower() in {"q", "quit", "exit"}:
                return 0

            else:
                print("Choix invalide.")

        except KeyboardInterrupt:
            print("\nAction interrompue.")
        except Exception as exc:
            print(f"Erreur menu: {exc}", file=sys.stderr)

        menu_input("\nEntrée pour revenir au menu...")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orphan Manager STRICT pour AllDebrid + Decypharr DFS")
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml", help="Chemin config YAML")
    parser.add_argument("--instance", type=str, help="Nom exact de l'instance à traiter")
    parser.add_argument("--execute", action="store_true", help="Supprime réellement les magnets orphelins candidats")
    parser.add_argument("--yes", "-y", action="store_true", help="Confirme automatiquement la suppression")
    parser.add_argument("--details", action="store_true", help="Affiche les orphelins candidats")
    parser.add_argument("--show-used", action="store_true", help="Affiche les magnets qui matchent exactement")
    parser.add_argument("--show-protected", action="store_true", help="Affiche les magnets protégés par âge")
    parser.add_argument("--export-json", type=str, help="Exporte un rapport JSON")
    parser.add_argument("--export-csv", type=str, help="Exporte un rapport CSV")
    parser.add_argument("--min-age-hours", type=int, default=None, help="Override protection âge minimum, mettre 0 pour désactiver")
    parser.add_argument("--debug-symlinks", action="store_true", help="Affiche stats/exemples de symlinks matchés")
    parser.add_argument("--debug-list", action="store_true", help="Liste les magnets AllDebrid via API")
    parser.add_argument("--test-path", type=str, help="Teste l'extraction depuis un symlink ou une cible")
    parser.add_argument("--menu", action="store_true", help="Ouvre le menu interactif")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    try:
        if args.menu or len(sys.argv) == 1:
            return await run_menu(args.config)

        return await run_once(args)
    except KeyboardInterrupt:
        await AllDebridAPI.close_all_sessions()
        print("\nInterrompu par l'utilisateur.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        try:
            asyncio.run(AllDebridAPI.close_all_sessions())
        except Exception:
            pass
        print("\nInterrompu par l'utilisateur.", file=sys.stderr)
        sys.exit(130)
