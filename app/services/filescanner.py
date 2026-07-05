import logging
import os
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


def scan_library_roots(roots: list[str], prefixes: list[str]) -> tuple[list[dict], int, int, int]:
    total = 0
    matching = 0
    broken = 0
    results: list[dict] = []

    for root in roots:
        for symlink_path in iter_symlinks(root):
            total += 1
            info = inspect_symlink(symlink_path, prefixes)
            if info["matches_prefix"]:
                matching += 1
                if info["broken"]:
                    broken += 1
                    results.append(info)

    return results, total, matching, broken
