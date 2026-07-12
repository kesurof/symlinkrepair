import logging
import os
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)


def iter_symlinks(root: str):
    root_path = Path(root).resolve()
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            for entry in os.scandir(current):
                if entry.is_symlink():
                    yield entry.path
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
        except OSError:
            continue


def inspect_symlink(path: str, prefixes: list[str]) -> dict:
    target = os.readlink(path)
    target_resolved = target
    if not os.path.isabs(target):
        target_resolved = os.path.join(os.path.dirname(path), target)
    target_resolved = os.path.normpath(target_resolved)

    exists = os.path.exists(target_resolved)
    matches = any(target_resolved.startswith(p) for p in prefixes if p)

    return {
        "symlink_path": path,
        "target_path": target,
        "target_resolved": target_resolved,
        "exists": exists,
        "broken": not exists,
        "matches_prefix": matches,
    }


def scan_library_roots(
    roots: list[str], prefixes: list[str], limit: int = 0
) -> tuple[list[dict], int, int, int]:
    total = 0
    matching = 0
    broken = 0
    results: list[dict] = []

    for root in roots:
        root_short = root.rstrip("/").rsplit("/", 1)[-1]
        for symlink_path in iter_symlinks(root):
            total += 1
            if total % 5000 == 0:
                logger.info("Scan progress: %d symlinks scanned on %s ...", total, root_short)
            info = inspect_symlink(symlink_path, prefixes)
            if info["matches_prefix"]:
                matching += 1
                if info["broken"]:
                    broken += 1
                    results.append(info)
                    if limit and len(results) >= limit:
                        logger.info(
                            "Scan finished (limit): %d symlinks, %d broken on %s",
                            total,
                            broken,
                            root_short,
                        )
                        return results, total, matching, broken

    logger.info(
        "Scan finished: %d symlinks, %d broken, %d matching",
        total,
        broken,
        matching,
    )
    return results, total, matching, broken


def _extract_group(target_path: str) -> str:
    marker = "/alldebrid/"
    try:
        idx = target_path.index(marker) + len(marker)
        end = target_path.index("/", idx) if "/" in target_path[idx:] else len(target_path)
        return target_path[:end]
    except ValueError:
        return str(Path(target_path).parent)


def analyze_symlink_targets(root: str) -> dict:
    root_path = Path(root).resolve()
    targets: Counter[str] = Counter()
    total = 0
    broken = 0
    broken_dirs: Counter[str] = Counter()

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
        entries = [os.path.join(dirpath, name) for name in dirnames + filenames]

        for link_path in entries:
            if not os.path.islink(link_path):
                continue

            total += 1
            raw_target = os.readlink(link_path)
            target = Path(raw_target)
            if not target.is_absolute():
                target = Path(dirpath) / target

            target = Path(os.path.abspath(target))
            group = _extract_group(str(target))
            targets[group] += 1

            if not target.exists():
                broken += 1
                broken_dirs[group] += 1

    target_list = [
        {"dir": d, "count": c, "broken": broken_dirs.get(d, 0)} for d, c in targets.most_common()
    ]

    return {
        "target_dirs": target_list,
        "total": total,
        "broken": broken,
    }
