from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.services.alldebrid import (
    AllDebridAPI,
    candidate_variants,
    magnet_candidate_names,
    magnet_id,
    magnet_primary_name,
    parse_age_hours,
    strict_key,
)

logger = logging.getLogger(__name__)


@dataclass
class SymlinkUsage:
    total_symlinks: int = 0
    matching_symlinks: int = 0
    used_strict_keys: Set[str] = field(default_factory=set)
    used_torrent_dirs: Set[str] = field(default_factory=set)
    sample_targets: List[str] = field(default_factory=list)


@dataclass
class MagnetCandidate:
    magnet_id: str
    primary_name: str
    raw: Dict
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
    protected_count: int
    orphan_count: int
    duration: float
    used: List[MagnetCandidate]
    protected: List[MagnetCandidate]
    orphans: List[MagnetCandidate]


class OrphanDetector:
    def __init__(self, instance_cfg, fallback_prefixes: Optional[List[str]] = None):
        self.name = instance_cfg.name or "default"
        self.library_roots = [Path(p) for p in instance_cfg.library_roots if p]
        prefixes = instance_cfg.target_prefixes or fallback_prefixes or []
        self.target_prefixes = sorted(prefixes, key=lambda p: len(p), reverse=True)
        self.api_key = instance_cfg.api_key
        self.min_age_hours = instance_cfg.min_age_hours
        self.rate_limit = instance_cfg.rate_limit

    def _is_under_path(self, path: str, prefix: str) -> bool:
        pn = os.path.normpath(path)
        pr = os.path.normpath(prefix)
        return pn == pr or pn.startswith(pr.rstrip("/") + "/")

    def _match_target_prefix(self, target: str) -> Optional[Tuple[str, Tuple[str, ...]]]:
        for prefix in self.target_prefixes:
            if self._is_under_path(target, prefix):
                pn = os.path.normpath(target)
                pr = os.path.normpath(prefix)
                rel = pn[len(pr.rstrip("/")) + 1 :] if pn != pr else ""
                parts = tuple(p for p in rel.split(os.sep) if p)
                return prefix, parts
        return None

    def scan_symlinks(self) -> SymlinkUsage:
        usage = SymlinkUsage()
        for base in self.library_roots:
            if not base.exists() or not base.is_dir():
                logger.warning("Library root does not exist: %s", base)
                continue
            logger.debug("Scanning symlinks under %s", base)
            for root, dirnames, filenames in os.walk(base, followlinks=False):
                for name in list(dirnames) + list(filenames):
                    full_path = os.path.join(root, name)
                    try:
                        if not os.path.islink(full_path):
                            continue
                        usage.total_symlinks += 1
                        raw_target = os.readlink(full_path)
                        target = os.path.normpath(
                            raw_target
                            if os.path.isabs(raw_target)
                            else os.path.join(root, raw_target)
                        )
                        matched = self._match_target_prefix(target)
                        if not matched:
                            continue
                        _prefix, parts = matched
                        if not parts:
                            continue
                        usage.matching_symlinks += 1
                        torrent_dir = parts[0]
                        file_name = parts[-1]
                        usage.used_torrent_dirs.add(torrent_dir)
                        for name_val in (torrent_dir, file_name, Path(file_name).stem):
                            for variant in candidate_variants(name_val):
                                key = strict_key(variant)
                                if key:
                                    usage.used_strict_keys.add(key)
                        if len(usage.sample_targets) < 20:
                            usage.sample_targets.append(target)
                    except OSError:
                        pass
        return usage

    def classify_magnet(self, magnet: Dict, usage: SymlinkUsage) -> MagnetCandidate:
        mid = magnet_id(magnet)
        primary = magnet_primary_name(magnet)
        names = magnet_candidate_names(magnet)
        keys = {strict_key(n) for n in names if strict_key(n)}
        age = parse_age_hours(magnet)

        matched_key = ""
        matched_name = ""
        for key in sorted(keys):
            if key in usage.used_strict_keys:
                matched_key = key
                matched_name = next((n for n in names if strict_key(n) == key), "")
                break

        if matched_key:
            status = "used"
        elif age is not None and age < self.min_age_hours:
            status = "protected"
        else:
            status = "orphan"

        return MagnetCandidate(
            magnet_id=mid,
            primary_name=primary,
            raw=magnet,
            candidate_keys=keys,
            age_hours=age,
            status=status,
            match_name=matched_name,
            match_key=matched_key,
        )

    async def run(self) -> ScanResult:
        start = time.time()
        logger.info("[%s] Scanning symlinks...", self.name)
        usage = self.scan_symlinks()
        logger.info(
            "[%s] Symlinks: total=%d matching=%d keys=%d",
            self.name,
            usage.total_symlinks,
            usage.matching_symlinks,
            len(usage.used_strict_keys),
        )

        logger.info("[%s] Fetching AllDebrid magnets...", self.name)
        async with AllDebridAPI(self.api_key, self.rate_limit) as api:
            magnets = await api.get_magnets()
        logger.info("[%s] Fetched %d magnets", self.name, len(magnets))

        classified = [self.classify_magnet(m, usage) for m in magnets]
        used = [c for c in classified if c.status == "used"]
        protected = [c for c in classified if c.status == "protected"]
        orphans = [c for c in classified if c.status == "orphan"]

        result = ScanResult(
            instance_name=self.name,
            total_symlinks=usage.total_symlinks,
            matching_symlinks=usage.matching_symlinks,
            used_torrent_count=len(usage.used_torrent_dirs),
            used_key_count=len(usage.used_strict_keys),
            total_magnets=len(magnets),
            used_count=len(used),
            protected_count=len(protected),
            orphan_count=len(orphans),
            duration=time.time() - start,
            used=sorted(used, key=lambda c: c.primary_name.lower()),
            protected=sorted(protected, key=lambda c: c.primary_name.lower()),
            orphans=sorted(orphans, key=lambda c: c.primary_name.lower()),
        )
        logger.info(
            "[%s] Done: used=%d protected=%d orphans=%d (%.1fs)",
            self.name,
            result.used_count,
            result.protected_count,
            result.orphan_count,
            result.duration,
        )
        return result
