#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# CONFIGURATION
# ============================================================
#
# Indique ici les dossiers qui CONTIENNENT les symlinks.
# Ce sont les dossiers Medias / bibliothèques Radarr-Sonarr,
# pas forcément les dossiers /mnt où rclone/Alldebrid monte les fichiers.
#
# Format :
#   "chemin|manager;chemin|manager"
#
# Exemples :
#   MEDIA_ROOTS = "/Medias/Films|radarr;/Medias/Series|sonarr"
#   MEDIA_ROOTS = "/data/Medias/Movies|radarr;/data/Medias/TV|sonarr"

MEDIA_ROOTS = "/home/user/Medias/Films|radarr;/home/user/Medias/Series|sonarr"
OUTPUT_FILE = "./symlink_scan_report.json"


# ============================================================
# SCANNER RAPIDE ET SIMPLE
# ============================================================

VALID_MANAGERS = {"radarr", "sonarr", "unknown"}


def parse_roots(config: str) -> list[dict[str, str]]:
    roots: list[dict[str, str]] = []

    for part in config.split(";"):
        part = part.strip()
        if not part:
            continue

        path, _, manager = part.partition("|")
        path = path.strip()
        manager = manager.strip().lower() or "unknown"

        if not path:
            continue

        if manager not in VALID_MANAGERS:
            manager = "unknown"

        roots.append({"path": path, "manager": manager})

    return roots


def resolve_target(symlink: Path) -> tuple[str, str, bool]:
    raw_target = os.readlink(symlink)
    target = Path(raw_target)

    if not target.is_absolute():
        target = symlink.parent / target

    return raw_target, str(target.resolve(strict=False)), target.exists()


def scan_root(path: str, manager: str) -> dict[str, Any]:
    root = Path(path).expanduser()

    result: dict[str, Any] = {
        "path": str(root),
        "manager": manager,
        "exists": root.is_dir(),
        "broken_symlinks": [],
        "errors": [],
        "summary": {
            "total_symlinks": 0,
            "valid_symlinks": 0,
            "broken_symlinks": 0,
        },
    }

    if not result["exists"]:
        result["errors"].append({"path": str(root), "error": "root_not_found"})
        return result

    stack = [root]

    while stack:
        current = stack.pop()

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            symlink = Path(entry.path)
                            raw_target, resolved_target, target_exists = resolve_target(symlink)

                            result["summary"]["total_symlinks"] += 1

                            if target_exists:
                                result["summary"]["valid_symlinks"] += 1
                            else:
                                result["summary"]["broken_symlinks"] += 1
                                result["broken_symlinks"].append({
                                    "symlink": str(symlink),
                                    "relative_path": os.path.relpath(entry.path, root),
                                    "target": resolved_target or raw_target,
                                    "target_raw": raw_target,
                                    "target_resolved": resolved_target,
                                    "target_exists": False,
                                    "manager": manager,
                                    "root": str(root),
                                })

                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))

                    except OSError as exc:
                        result["errors"].append({
                            "path": entry.path,
                            "error": exc.__class__.__name__,
                        })

        except (FileNotFoundError, PermissionError, OSError) as exc:
            result["errors"].append({
                "path": str(current),
                "error": exc.__class__.__name__,
            })

    return result


def scan_all(config: str) -> dict[str, Any]:
    roots = parse_roots(config)

    report: dict[str, Any] = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "roots": [],
        "broken_symlinks": [],
        "errors": [],
        "summary": {
            "roots_configured": len(roots),
            "roots_scanned": 0,
            "total_symlinks": 0,
            "valid_symlinks": 0,
            "broken_symlinks": 0,
            "errors": 0,
            "by_manager": {
                "radarr": {"total": 0, "valid": 0, "broken": 0},
                "sonarr": {"total": 0, "valid": 0, "broken": 0},
                "unknown": {"total": 0, "valid": 0, "broken": 0},
            },
        },
    }

    for root in roots:
        root_report = scan_root(root["path"], root["manager"])

        report["roots"].append({
            "path": root_report["path"],
            "manager": root_report["manager"],
            "exists": root_report["exists"],
            "errors": root_report["errors"],
            "summary": root_report["summary"],
        })

        report["broken_symlinks"].extend(root_report["broken_symlinks"])

        for error in root_report["errors"]:
            report["errors"].append({
                "root": root_report["path"],
                "manager": root_report["manager"],
                **error,
            })

        manager = root_report["manager"]
        if manager not in VALID_MANAGERS:
            manager = "unknown"

        total = root_report["summary"]["total_symlinks"]
        valid = root_report["summary"]["valid_symlinks"]
        broken = root_report["summary"]["broken_symlinks"]

        report["summary"]["total_symlinks"] += total
        report["summary"]["valid_symlinks"] += valid
        report["summary"]["broken_symlinks"] += broken

        report["summary"]["by_manager"][manager]["total"] += total
        report["summary"]["by_manager"][manager]["valid"] += valid
        report["summary"]["by_manager"][manager]["broken"] += broken

    report["summary"]["roots_scanned"] = len(report["roots"])
    report["summary"]["errors"] = len(report["errors"])

    return report


def save_report(report: dict[str, Any], output_file: str) -> None:
    output = Path(output_file)
    output.parent.mkdir(parents=True, exist_ok=True)

    tmp = output.with_suffix(output.suffix + ".tmp")

    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    tmp.replace(output)


def print_result(report: dict[str, Any]) -> None:
    summary = report["summary"]

    print("")
    print("Scan terminé")
    print("============")
    print(f"Dossiers configurés : {summary['roots_configured']}")
    print(f"Dossiers scannés    : {summary['roots_scanned']}")
    print(f"Symlinks trouvés    : {summary['total_symlinks']}")
    print(f"Symlinks valides    : {summary['valid_symlinks']}")
    print(f"Symlinks cassés     : {summary['broken_symlinks']}")
    print(f"Erreurs             : {summary['errors']}")

    if report["broken_symlinks"]:
        print("")
        print("Symlinks cassés")
        print("---------------")
        for item in report["broken_symlinks"]:
            print(f"- {item['symlink']}")
            print(f"  cible : {item['target']}")


def main() -> int:
    media_roots = os.getenv("MEDIA_ROOTS", MEDIA_ROOTS)
    output_file = os.getenv("OUTPUT_FILE", OUTPUT_FILE)

    if not media_roots.strip():
        print("Erreur : MEDIA_ROOTS est vide.")
        return 1

    report = scan_all(media_roots)
    save_report(report, output_file)
    print_result(report)

    print("")
    print(f"Rapport JSON : {output_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
