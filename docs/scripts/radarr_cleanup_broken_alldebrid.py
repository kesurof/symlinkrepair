#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "radarr_cleanup.json"

DEFAULTS = {
    "RADARR_URL": "http://127.0.0.1:7878",
    "RADARR_API_KEY": "",
    "RADARR_CONTAINER": "radarr",
    "RADARR_LIBRARY_ROOTS": [
        "/home/USER/Medias/Films",
        "/home/USER/Medias/ANIMATION_Films",
    ],
    "RADARR_TARGET_PREFIXES": [
        "/mnt/decypharr/alldebrid/",
    ],
    "DISCORD_WEBHOOK_URL": "",
    "DISCORD_NOTIFICATIONS_ENABLED": False,
}

TMP_DB = "/tmp/radarr_cleanup_fresh.db"


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def mask_secret(value):
    if not value:
        return "NON CONFIGURÉE"
    if len(value) <= 8:
        return "********"
    return value[:4] + "..." + value[-4:]


def clean_path_list(value):
    if value is None or not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        item = str(item).strip().rstrip("/")
        if item and item not in cleaned:
            cleaned.append(item)

    return cleaned


def clean_prefix_list(value):
    prefixes = clean_path_list(value)
    return [prefix.rstrip("/") + "/" for prefix in prefixes]


def parse_bool(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in ["1", "true", "yes", "y", "on", "o", "oui"]

    return bool(value)


def target_matches_prefixes(target, prefixes):
    for prefix in prefixes:
        if target.startswith(prefix):
            return True, prefix
    return False, ""


def normalize_config(config):
    normalized = dict(DEFAULTS)

    for key in DEFAULTS:
        if key in config:
            normalized[key] = config[key]

    normalized["RADARR_URL"] = str(normalized.get("RADARR_URL", "")).strip()
    normalized["RADARR_API_KEY"] = str(normalized.get("RADARR_API_KEY", "")).strip()
    normalized["RADARR_CONTAINER"] = str(normalized.get("RADARR_CONTAINER", "")).strip()
    normalized["DISCORD_WEBHOOK_URL"] = str(normalized.get("DISCORD_WEBHOOK_URL", "")).strip()
    normalized["DISCORD_NOTIFICATIONS_ENABLED"] = parse_bool(
        normalized.get("DISCORD_NOTIFICATIONS_ENABLED", False)
    )

    normalized["RADARR_LIBRARY_ROOTS"] = clean_path_list(
        normalized.get("RADARR_LIBRARY_ROOTS", [])
    )

    normalized["RADARR_TARGET_PREFIXES"] = clean_prefix_list(
        normalized.get("RADARR_TARGET_PREFIXES", [])
    )

    return normalized


def load_config():
    config = dict(DEFAULTS)

    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as file:
                loaded = json.load(file)

            if isinstance(loaded, dict):
                config.update({
                    key: value
                    for key, value in loaded.items()
                    if key in DEFAULTS
                })
        except json.JSONDecodeError as error:
            log(f"AVERTISSEMENT: configuration JSON illisible: {CONFIG_FILE} | {error}")

    for key in [
        "RADARR_URL",
        "RADARR_API_KEY",
        "RADARR_CONTAINER",
        "DISCORD_WEBHOOK_URL",
        "DISCORD_NOTIFICATIONS_ENABLED",
    ]:
        if key in os.environ:
            config[key] = os.environ[key]

    return normalize_config(config)


def save_config(config):
    normalized = normalize_config(config)

    with CONFIG_FILE.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2, ensure_ascii=False)
        file.write("\n")

    os.chmod(CONFIG_FILE, 0o600)
    log(f"Configuration enregistrée : {CONFIG_FILE}")


def prompt_scalar_setting(label, current_value, secret=False):
    shown = mask_secret(current_value) if secret else current_value
    entered = input(f"{label} [{shown}] : ").strip()
    return entered if entered else current_value


def prompt_path_list(title, current_items, example):
    current_items = clean_path_list(current_items)

    print()
    print(title)
    print("-" * len(title))

    if current_items:
        print("Valeurs actuelles :")
        for index, item in enumerate(current_items, start=1):
            print(f"  {index}. {item}")
    else:
        print("Aucune valeur configurée.")

    print()
    print("Entrée vide = garder la liste actuelle.")
    print("Tape R pour remplacer la liste.")
    print(f"Exemple : {example}")

    action = input("Ton choix [Entrée = garder / R = remplacer] : ").strip().lower()

    if action not in ["r", "remplacer"]:
        return current_items

    print()
    print("Entre les chemins un par un.")
    print("Quand tu as terminé, laisse vide puis appuie sur Entrée.")

    new_items = []
    index = 1

    while True:
        value = input(f"Chemin {index} : ").strip()

        if not value:
            break

        cleaned = value.rstrip("/")

        if cleaned not in new_items:
            new_items.append(cleaned)

        index += 1

    if not new_items:
        print("Aucun chemin saisi : la liste actuelle est conservée.")
        return current_items

    return new_items


def setup_config():
    current = load_config()

    print()
    print("Configuration Radarr")
    print("--------------------")
    print("Laisse vide pour garder la valeur actuelle.")
    print()

    new_config = {}

    new_config["RADARR_URL"] = prompt_scalar_setting(
        "Adresse de Radarr",
        current.get("RADARR_URL", DEFAULTS["RADARR_URL"]),
    )

    new_config["RADARR_API_KEY"] = prompt_scalar_setting(
        "Clé API Radarr",
        current.get("RADARR_API_KEY", ""),
        secret=True,
    )

    new_config["RADARR_CONTAINER"] = prompt_scalar_setting(
        "Nom du conteneur Docker Radarr",
        current.get("RADARR_CONTAINER", DEFAULTS["RADARR_CONTAINER"]),
    )

    new_config["DISCORD_WEBHOOK_URL"] = prompt_scalar_setting(
        "Webhook Discord",
        current.get("DISCORD_WEBHOOK_URL", ""),
        secret=True,
    )

    new_config["DISCORD_NOTIFICATIONS_ENABLED"] = ask_yes_no(
        "Activer les notifications Discord",
        current.get("DISCORD_NOTIFICATIONS_ENABLED", False),
    )

    new_config["RADARR_LIBRARY_ROOTS"] = prompt_path_list(
        "Dossiers racines des films à analyser",
        current.get("RADARR_LIBRARY_ROOTS", []),
        "/home/USER/Medias/Films",
    )

    new_config["RADARR_TARGET_PREFIXES"] = prompt_path_list(
        "Préfixes des liens AllDebrid / Decypharr à surveiller",
        current.get("RADARR_TARGET_PREFIXES", []),
        "/mnt/decypharr/alldebrid/",
    )

    save_config(new_config)

    print()
    print("Configuration terminée.")
    print(f"Nouveau fichier de configuration : {CONFIG_FILE}")


def run_cmd(cmd, check=True):
    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Commande échouée: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


def api_request(method, base_url, api_key, endpoint, payload=None):
    endpoint = endpoint.lstrip("/")
    full_url = f"{base_url.rstrip('/')}/api/v3/{endpoint}"

    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json",
    }

    body = None

    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        full_url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")

            if not raw:
                return response.status, None

            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw

    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw

        return error.code, parsed

    except urllib.error.URLError as error:
        raise RuntimeError(f"Impossible de joindre Radarr: {error}") from error


def should_send_discord_notification(config):
    return bool(
        config.get("DISCORD_NOTIFICATIONS_ENABLED")
        and config.get("DISCORD_WEBHOOK_URL")
    )


def build_execution_summary(
    config,
    apply=False,
    max_files=0,
    tag_ids=None,
    movie_title="",
    keep_symlinks=False,
    skip_rescan=False,
    skip_search=False,
):
    return {
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "apply" if apply else "dry_run",
        "status": "running",
        "radarr_url": config.get("RADARR_URL", ""),
        "radarr_version": "",
        "max_files": max_files,
        "tag_ids": list(tag_ids or []),
        "movie_title": movie_title,
        "keep_symlinks": keep_symlinks,
        "skip_rescan": skip_rescan,
        "skip_search": skip_search,
        "library_roots": [],
        "missing_roots": [],
        "target_prefixes": [],
        "symlinks_total": 0,
        "symlinks_matching_prefix": 0,
        "broken_symlinks": 0,
        "targets_before_limit": 0,
        "targets_selected": 0,
        "affected_movies": 0,
        "reason_counts": {},
        "moviefiles_processed": 0,
        "delete_http_counts": {},
        "unlink_counts": {},
        "refresh_count": 0,
        "search_count": 0,
        "queue_total_records": None,
        "report_path": "",
        "error": "",
        "finished_at": "",
    }


def format_counter_lines(counter_dict):
    if not counter_dict:
        return "-"

    return "\n".join(
        f"`{key}`: **{value}**"
        for key, value in sorted(counter_dict.items())
    )


def format_list_preview(values, empty_label="Tous"):
    if not values:
        return empty_label

    rendered = ", ".join(str(value) for value in values)
    return rendered[:1024]


def send_discord_webhook(webhook_url, summary):
    status = summary.get("status", "unknown")
    mode = "NETTOYAGE RÉEL" if summary.get("mode") == "apply" else "SIMULATION"
    if status == "error":
        color = 0xED4245
        status_badge = "🔴 ERREUR"
    elif summary.get("mode") == "apply":
        color = 0xFEE75C
        status_badge = "🟡 NETTOYAGE"
    else:
        color = 0x57F287
        status_badge = "🟢 SIMULATION"

    title = f"{status_badge} | Radarr Cleanup"

    overview_lines = [
        f"**Mode**: {mode}",
        f"**Statut**: `{status.upper()}`",
        f"**Debut**: {summary.get('started_at') or '-'}",
    ]

    if summary.get("finished_at"):
        overview_lines.append(f"**Fin**: {summary.get('finished_at')}")

    fields = [
        {
            "name": "Vue d'ensemble",
            "value": "\n".join(overview_lines),
            "inline": False,
        },
        {
            "name": "📡 Detection",
            "value": (
                f"**Symlinks total**: **{summary.get('symlinks_total', 0)}**\n"
                f"**Vers prefixe surveille**: **{summary.get('symlinks_matching_prefix', 0)}**\n"
                f"**Symlinks casses**: **{summary.get('broken_symlinks', 0)}**"
            ),
            "inline": True,
        },
        {
            "name": "🎯 Ciblage",
            "value": (
                f"**Avant limite**: **{summary.get('targets_before_limit', 0)}**\n"
                f"**Selectionnes**: **{summary.get('targets_selected', 0)}**\n"
                f"**Films touches**: **{summary.get('affected_movies', 0)}**"
            ),
            "inline": True,
        },
        {
            "name": "🛠️ Actions",
            "value": (
                f"**Traites API**: **{summary.get('moviefiles_processed', 0)}**\n"
                f"**RefreshMovie**: **{summary.get('refresh_count', 0)}**\n"
                f"**MoviesSearch**: **{summary.get('search_count', 0)}**"
            ),
            "inline": True,
        },
        {
            "name": "🔎 Filtres",
            "value": (
                f"**Tags**: {format_list_preview(summary.get('tag_ids') or [], 'Tous')}\n"
                f"**Titre**: {summary.get('movie_title') or 'Aucun'}\n"
                f"**Max files**: {summary.get('max_files', 0) or 'Illimite'}"
            ),
            "inline": False,
        },
    ]

    report_path = summary.get("report_path")
    if report_path:
        fields.append({
            "name": "📄 Rapport",
            "value": f"`{report_path[:1018]}`",
            "inline": False,
        })

    delete_http_counts = summary.get("delete_http_counts") or {}
    if delete_http_counts:
        fields.append({
            "name": "🌐 HTTP suppressions",
            "value": format_counter_lines(delete_http_counts),
            "inline": True,
        })

    unlink_counts = summary.get("unlink_counts") or {}
    if unlink_counts:
        fields.append({
            "name": "🧹 Symlinks locaux",
            "value": format_counter_lines(unlink_counts),
            "inline": True,
        })

    reason_counts = summary.get("reason_counts") or {}
    if reason_counts:
        fields.append({
            "name": "📌 Raisons",
            "value": format_counter_lines(reason_counts),
            "inline": True,
        })

    error_message = summary.get("error")
    if error_message:
        fields.append({
            "name": "🚨 Erreur",
            "value": f"```\n{error_message[:1016]}\n```",
            "inline": False,
        })

    description = (
        f"**{summary.get('targets_selected', 0)}** MovieFiles selectionnes, "
        f"**{summary.get('broken_symlinks', 0)}** symlinks casses detectes."
    )

    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {
                "text": (
                    f"Radarr: {summary.get('radarr_url') or '-'}"
                    f" | Version: {summary.get('radarr_version') or '-'}"
                )
            },
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }]
    }

    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "radarr-cleanup/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
        if response.status not in [200, 204]:
            raise RuntimeError(f"Webhook Discord HTTP={response.status}")


def notify_discord_summary(config, summary):
    if not should_send_discord_notification(config):
        return

    try:
        send_discord_webhook(config["DISCORD_WEBHOOK_URL"], summary)
        log("Notification Discord envoyée.")
    except Exception as error:
        log(f"AVERTISSEMENT: envoi Discord impossible: {error}")


def ensure_config(config):
    if not config.get("RADARR_API_KEY"):
        print()
        print("ERREUR : clé API Radarr absente.")
        print("Lance d'abord :")
        print("./radarr_cleanup_broken_alldebrid.py --setup")
        print()
        return False

    return True


def print_config(config):
    print()
    print("Configuration actuelle")
    print("----------------------")
    print(f"RADARR_URL             = {config['RADARR_URL']}")
    print(f"RADARR_API_KEY         = {mask_secret(config['RADARR_API_KEY'])}")
    print(f"RADARR_CONTAINER       = {config['RADARR_CONTAINER']}")
    print(f"DISCORD_WEBHOOK_URL    = {mask_secret(config['DISCORD_WEBHOOK_URL'])}")
    print(f"DISCORD_NOTIFICATIONS  = {config['DISCORD_NOTIFICATIONS_ENABLED']}")
    print(f"RADARR_LIBRARY_ROOTS   = {clean_path_list(config.get('RADARR_LIBRARY_ROOTS'))}")
    print(f"RADARR_TARGET_PREFIXES = {clean_prefix_list(config.get('RADARR_TARGET_PREFIXES'))}")
    print(f"CONFIG_FILE            = {CONFIG_FILE}")

    roots = clean_path_list(config.get("RADARR_LIBRARY_ROOTS"))
    prefixes = clean_prefix_list(config.get("RADARR_TARGET_PREFIXES"))

    print()
    print("Dossiers Radarr analysés :")
    for root in roots:
        exists = "OK" if Path(root).is_dir() else "INTROUVABLE"
        print(f"  - {root} [{exists}]")

    print()
    print("Préfixes de symlinks surveillés :")
    for prefix in prefixes:
        print(f"  - {prefix}")

    print()


def test_api(config):
    status, body = api_request(
        "GET",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        "system/status",
    )

    if status != 200:
        print(f"ERREUR API Radarr HTTP={status}")
        print(body)
        return False

    print()
    print("API Radarr OK")
    print(f"Version : {body.get('version')}")
    print(f"AppData : {body.get('appData')}")
    print(f"Docker  : {body.get('isDocker')}")
    print()

    return True


def get_tags(config):
    status, body = api_request(
        "GET",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        "tag",
    )

    if status != 200 or not isinstance(body, list):
        return []

    tags = []

    for tag in body:
        tag_id = tag.get("id")
        label = tag.get("label")

        if tag_id is not None and label:
            tags.append({
                "id": int(tag_id),
                "label": str(label),
            })

    return sorted(tags, key=lambda item: item["label"].lower())


def parse_int_list(value):
    if not value:
        return []

    result = []

    for part in value.split(","):
        part = part.strip()

        if part.isdigit():
            result.append(int(part))

    return sorted(set(result))


def choose_tags_interactive(config):
    tags = get_tags(config)

    print()
    print("Filtre par tags Radarr")
    print("----------------------")
    print("Laisse vide pour traiter tous les films, sans filtre par tag.")

    if not tags:
        print()
        print("Aucun tag récupéré depuis Radarr.")
        value = input("Tags à utiliser, vide = tous les films : ").strip()
        return parse_int_list(value)

    print()
    print("Tags disponibles :")
    for tag in tags:
        print(f"  {tag['id']:>4}  {tag['label']}")

    print()
    print("Entre le ou les IDs de tags à utiliser, séparés par une virgule.")
    print("Exemple : 6 ou 6,8,12")
    value = input("Tags à utiliser, vide = tous les films : ").strip()

    return parse_int_list(value)


def ask_int(prompt, default=0):
    value = input(f"{prompt} [{default}] : ").strip()

    if not value:
        return default

    if not value.isdigit():
        return default

    return int(value)


def ask_text(prompt, default=""):
    if default:
        value = input(f"{prompt} [{default}] : ").strip()
    else:
        value = input(f"{prompt} : ").strip()

    return value if value else default


def ask_yes_no(prompt, default=False):
    suffix = "o/N" if not default else "O/n"
    value = input(f"{prompt} ({suffix}) : ").strip().lower()

    if not value:
        return default

    return value in ["o", "oui", "y", "yes"]


def docker_file_exists(container, path):
    result = run_cmd(
        ["docker", "exec", container, "test", "-f", path],
        check=False,
    )
    return result.returncode == 0


def copy_fresh_db(container, db_path):
    for suffix in ["", "-wal", "-shm"]:
        candidate = db_path + suffix
        if os.path.exists(candidate):
            os.remove(candidate)

    log(f"Copie DB fraîche : {container}:/config/radarr.db -> {db_path}")

    run_cmd([
        "docker",
        "cp",
        f"{container}:/config/radarr.db",
        db_path,
    ])

    optional_files = [
        ("/config/radarr.db-wal", db_path + "-wal"),
        ("/config/radarr.db-shm", db_path + "-shm"),
    ]

    for source, target in optional_files:
        if docker_file_exists(container, source):
            log(f"Copie fichier SQLite optionnel : {source}")
            run_cmd([
                "docker",
                "cp",
                f"{container}:{source}",
                target,
            ])

    if not os.path.exists(db_path):
        raise RuntimeError(f"DB introuvable après copie : {db_path}")


def parse_json_array(value):
    if value is None:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return []


def load_radarr_records(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT
            mf.Id AS movie_file_id,
            mf.MovieId AS movie_id,
            mf.RelativePath AS relative_path,
            mf.Size AS size,
            mf.Quality AS quality,
            mf.Languages AS languages,
            m.Path AS movie_path,
            m.Tags AS movie_tags,
            mm.Title AS movie_title,
            mm.Year AS movie_year,
            mm.ImdbId AS imdb_id,
            mm.TmdbId AS tmdb_id
        FROM MovieFiles mf
        JOIN Movies m ON m.Id = mf.MovieId
        LEFT JOIN MovieMetadata mm ON mm.Id = m.MovieMetadataId
    """).fetchall()

    connection.close()

    records = []
    records_by_path = {}

    for row in rows:
        movie_path = row["movie_path"]
        relative_path = row["relative_path"]

        if not movie_path or not relative_path:
            continue

        full_path = f"{movie_path.rstrip('/')}/{relative_path.lstrip('/')}"

        movie_tags = [
            int(value)
            for value in parse_json_array(row["movie_tags"])
            if str(value).isdigit()
        ]

        record = {
            "movie_file_id": int(row["movie_file_id"]),
            "movie_id": int(row["movie_id"]),
            "movie_title": row["movie_title"] or "",
            "movie_year": row["movie_year"] or "",
            "imdb_id": row["imdb_id"] or "",
            "tmdb_id": row["tmdb_id"] or "",
            "movie_tags": sorted(set(movie_tags)),
            "movie_path": movie_path,
            "relative_path": relative_path,
            "full_path": full_path,
            "size": int(row["size"] or 0),
            "quality": row["quality"] or "",
            "languages": row["languages"] or "",
        }

        records.append(record)
        records_by_path[full_path] = record

    return records, records_by_path


def iter_symlinks(root):
    stack = [root]

    while stack:
        current = stack.pop()

        try:
            with os.scandir(current) as iterator:
                for entry in iterator:
                    try:
                        if entry.is_symlink():
                            yield entry.path
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError as error:
                        log(f"SKIP entrée filesystem : {entry.path} | {error}")
        except OSError as error:
            log(f"SKIP dossier : {current} | {error}")


def symlink_info(path, target_prefixes):
    prefixes = clean_prefix_list(target_prefixes)

    info = {
        "path": path,
        "is_symlink": False,
        "target": "",
        "target_matches": False,
        "matched_prefix": "",
        "exists": False,
        "broken": False,
        "io_error": False,
    }

    if not os.path.islink(path):
        return info

    info["is_symlink"] = True

    try:
        target = os.readlink(path)
    except OSError as error:
        info["io_error"] = True
        info["target"] = f"READLINK_ERROR: {error}"
        return info

    if not os.path.isabs(target):
        target = os.path.abspath(os.path.join(os.path.dirname(path), target))

    info["target"] = target

    matches, matched_prefix = target_matches_prefixes(target, prefixes)
    info["target_matches"] = matches
    info["matched_prefix"] = matched_prefix

    try:
        os.stat(path)
        info["exists"] = True
        info["broken"] = False
    except FileNotFoundError:
        info["exists"] = False
        info["broken"] = True
    except OSError:
        info["exists"] = False
        info["io_error"] = True
        info["broken"] = False

    return info


def collect_broken_symlinks(library_roots, target_prefixes):
    roots = clean_path_list(library_roots)
    broken = {}
    totals = Counter()

    for root in roots:
        root_path = Path(root)

        if not root_path.is_dir():
            log(f"SKIP chemin Radarr introuvable : {root}")
            continue

        for path in iter_symlinks(root):
            totals["symlinks_total"] += 1
            info = symlink_info(path, target_prefixes)

            if info["target_matches"]:
                totals["symlinks_matching_prefix"] += 1

            if info["target_matches"] and info["broken"]:
                totals["symlinks_broken"] += 1
                broken[path] = info

    return broken, totals


def record_matches_filters(record, tag_ids=None, movie_title=""):
    tag_ids = tag_ids or []

    if tag_ids:
        if not set(tag_ids).intersection(set(record["movie_tags"])):
            return False

    if movie_title:
        if movie_title.lower() not in record["movie_title"].lower():
            return False

    return True


def choose_targets(records_by_path, broken_symlinks, tag_ids, movie_title):
    targets = []

    for path, info in broken_symlinks.items():
        record = records_by_path.get(path)

        if not record:
            continue

        if not record_matches_filters(record, tag_ids, movie_title):
            continue

        targets.append({
            **record,
            "symlink_target": info["target"],
            "reason": "broken_symlink",
        })

    return unique_targets(targets)


def unique_targets(targets):
    seen = set()
    result = []

    for target in targets:
        movie_file_id = target["movie_file_id"]

        if movie_file_id in seen:
            continue

        seen.add(movie_file_id)
        result.append(target)

    return result


def apply_max_files_limit(targets, max_files):
    if not max_files or max_files <= 0:
        return targets, False

    return targets[:max_files], len(targets) > max_files


def delete_movie_file(config, movie_file_id):
    return api_request(
        "DELETE",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        f"moviefile/{movie_file_id}?deleteFile=false",
    )


def post_command(config, payload):
    return api_request(
        "POST",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        "command",
        payload=payload,
    )


def unlink_symlink_if_allowed(path, target_prefixes):
    info = symlink_info(path, target_prefixes)

    if not info["is_symlink"]:
        return "not_symlink"

    if not info["target_matches"]:
        return "target_not_allowed"

    try:
        os.unlink(path)
        return "removed"
    except FileNotFoundError:
        return "already_missing"
    except OSError as error:
        return f"error: {error}"


def write_report(report_path, targets, results):
    with open(report_path, "w", encoding="utf-8") as file:
        file.write(
            "movieFileId\tmovieId\ttitle\tyear\timdbId\ttmdbId\tmovieTags\t"
            "fullPath\tsymlinkTarget\treason\tdeleteHttp\tunlinkStatus\n"
        )

        for target in targets:
            movie_file_id = target["movie_file_id"]
            result = results.get(movie_file_id, {})

            file.write(
                f"{movie_file_id}\t"
                f"{target['movie_id']}\t"
                f"{target['movie_title']}\t"
                f"{target['movie_year']}\t"
                f"{target['imdb_id']}\t"
                f"{target['tmdb_id']}\t"
                f"{','.join(map(str, target['movie_tags']))}\t"
                f"{target['full_path']}\t"
                f"{target.get('symlink_target', '')}\t"
                f"{target.get('reason', '')}\t"
                f"{result.get('delete_http', '')}\t"
                f"{result.get('unlink_status', '')}\n"
            )


def run_cleanup(
    config,
    apply=False,
    max_files=0,
    tag_ids=None,
    movie_title="",
    keep_symlinks=False,
    skip_rescan=False,
    skip_search=False,
):
    tag_ids = tag_ids or []
    dry_run = not apply
    summary = build_execution_summary(
        config=config,
        apply=apply,
        max_files=max_files,
        tag_ids=tag_ids,
        movie_title=movie_title,
        keep_symlinks=keep_symlinks,
        skip_rescan=skip_rescan,
        skip_search=skip_search,
    )

    started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"/tmp/radarr_cleanup_report_{started_at}.tsv"
    summary["report_path"] = report_path

    log("Démarrage traitement Radarr")
    log(f"Mode: {'NETTOYAGE RÉEL' if apply else 'SIMULATION'}")
    log(f"Max files: {'illimité' if max_files == 0 else max_files}")
    log(f"Tags inclus: {tag_ids if tag_ids else 'tous'}")
    log(f"Filtre titre: {movie_title if movie_title else 'aucun'}")

    library_roots = clean_path_list(config.get("RADARR_LIBRARY_ROOTS"))
    target_prefixes = clean_prefix_list(config.get("RADARR_TARGET_PREFIXES"))
    summary["library_roots"] = list(library_roots)
    summary["target_prefixes"] = list(target_prefixes)

    existing_roots = [root for root in library_roots if Path(root).is_dir()]
    missing_roots = [root for root in library_roots if not Path(root).is_dir()]
    summary["missing_roots"] = list(missing_roots)

    if missing_roots:
        for root in missing_roots:
            log(f"AVERTISSEMENT: chemin Radarr introuvable, ignoré: {root}")

    if not existing_roots:
        log("ERREUR: aucun dossier racine Radarr valide à analyser.")
        log("Corrige RADARR_LIBRARY_ROOTS avec --setup.")
        summary["status"] = "error"
        summary["error"] = "Aucun dossier racine Radarr valide à analyser."
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return 1, summary

    if not target_prefixes:
        log("ERREUR: aucun préfixe AllDebrid / Decypharr configuré.")
        log("Corrige RADARR_TARGET_PREFIXES avec --setup.")
        summary["status"] = "error"
        summary["error"] = "Aucun préfixe AllDebrid / Decypharr configuré."
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return 1, summary

    log(f"Dossiers Radarr analysés: {existing_roots}")
    log(f"Préfixes de symlinks surveillés: {target_prefixes}")

    status, body = api_request(
        "GET",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        "system/status",
    )

    if status != 200:
        log(f"ERREUR API Radarr HTTP={status}")
        print(body)
        summary["status"] = "error"
        summary["error"] = f"ERREUR API Radarr HTTP={status}"
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return 1, summary

    log(f"Radarr OK version={body.get('version')}")
    summary["radarr_version"] = body.get("version") or ""

    copy_fresh_db(config["RADARR_CONTAINER"], TMP_DB)

    records, records_by_path = load_radarr_records(TMP_DB)
    log(f"MovieFiles chargés depuis DB: {len(records)}")

    broken_symlinks, symlink_totals = collect_broken_symlinks(
        existing_roots,
        target_prefixes,
    )

    log(f"Symlinks total détectés: {symlink_totals.get('symlinks_total', 0)}")
    log(f"Symlinks vers préfixe surveillé: {symlink_totals.get('symlinks_matching_prefix', 0)}")
    log(f"Symlinks cassés vers AllDebrid détectés: {len(broken_symlinks)}")
    summary["symlinks_total"] = symlink_totals.get("symlinks_total", 0)
    summary["symlinks_matching_prefix"] = symlink_totals.get("symlinks_matching_prefix", 0)
    summary["broken_symlinks"] = len(broken_symlinks)

    targets = choose_targets(
        records_by_path=records_by_path,
        broken_symlinks=broken_symlinks,
        tag_ids=tag_ids,
        movie_title=movie_title,
    )

    total_targets_before_limit = len(targets)
    summary["targets_before_limit"] = total_targets_before_limit

    targets, max_limit_applied = apply_max_files_limit(
        targets=targets,
        max_files=max_files,
    )

    if max_limit_applied:
        log(
            "Limite appliquée: "
            f"{len(targets)}/{total_targets_before_limit} MovieFiles sélectionnés"
        )

    affected_movies = sorted({
        (target["movie_id"], target["movie_title"], target["movie_year"])
        for target in targets
    })

    reason_counts = Counter(target["reason"] for target in targets)
    summary["targets_selected"] = len(targets)
    summary["affected_movies"] = len(affected_movies)
    summary["reason_counts"] = dict(reason_counts)

    log("Résumé avant action")
    log(f"Broken symlinks matchés dans Radarr: {total_targets_before_limit}")
    log(f"MovieFiles à traiter: {len(targets)}")
    log(f"Films touchés: {len(affected_movies)}")
    log(f"Raisons: {dict(reason_counts)}")
    log(f"Rapport prévu: {report_path}")

    if not targets:
        log("Aucune cible à traiter.")
        write_report(report_path, [], {})
        log(f"Rapport écrit: {report_path}")
        summary["status"] = "success"
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return 0, summary

    print()
    print("Aperçu limité des 20 premières cibles")
    print("--------------------------------------")

    for target in targets[:20]:
        print(
            f"MFID={target['movie_file_id']} "
            f"MID={target['movie_id']} "
            f"{target['movie_title']} ({target['movie_year']}) "
            f"reason={target['reason']}"
        )

    print()

    if dry_run:
        log("SIMULATION : aucune suppression, aucun scan, aucune recherche.")
        write_report(report_path, targets, {})
        log(f"Rapport écrit: {report_path}")
        summary["status"] = "success"
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return 0, summary

    results = {}

    log("Suppression des MovieFiles Radarr")

    for index, target in enumerate(targets, start=1):
        movie_file_id = target["movie_file_id"]
        full_path = target["full_path"]

        info = symlink_info(full_path, target_prefixes)

        if not info["is_symlink"]:
            log(f"[{index}/{len(targets)}] SKIP MFID={movie_file_id} not_symlink")
            continue

        if not info["target_matches"]:
            log(f"[{index}/{len(targets)}] SKIP MFID={movie_file_id} target_not_allowed")
            continue

        if not info["broken"]:
            log(f"[{index}/{len(targets)}] SKIP MFID={movie_file_id} not_broken")
            continue

        log(
            f"[{index}/{len(targets)}] DELETE MFID={movie_file_id} "
            f"{target['movie_title']} ({target['movie_year']})"
        )

        http_status, response_body = delete_movie_file(config, movie_file_id)

        unlink_status = "kept"

        if not keep_symlinks:
            unlink_status = unlink_symlink_if_allowed(
                full_path,
                target_prefixes,
            )

        results[movie_file_id] = {
            "delete_http": http_status,
            "delete_body": response_body,
            "unlink_status": unlink_status,
        }

        log(f"     HTTP={http_status} unlink={unlink_status}")

        time.sleep(0.05)

    refresh_results = []

    if not skip_rescan:
        log("RefreshMovie ciblé des films touchés")

        for movie_id, movie_title, movie_year in affected_movies:
            payload = {
                "name": "RefreshMovie",
                "movieIds": [movie_id],
            }

            http_status, body = post_command(config, payload)
            command_id = body.get("id") if isinstance(body, dict) else None

            refresh_results.append({
                "movie_id": movie_id,
                "movie_title": movie_title,
                "movie_year": movie_year,
                "http": http_status,
                "command_id": command_id,
            })

            log(
                f"     RefreshMovie MID={movie_id} "
                f"{movie_title} ({movie_year}) "
                f"HTTP={http_status} commandId={command_id}"
            )

            time.sleep(0.10)

    search_results = []

    if not skip_search and affected_movies:
        log("Recherche automatique Radarr des films touchés")

        movie_ids = [movie_id for movie_id, _, _ in affected_movies]

        payload = {
            "name": "MoviesSearch",
            "movieIds": movie_ids,
        }

        http_status, body = post_command(config, payload)
        command_id = body.get("id") if isinstance(body, dict) else None

        search_results.append({
            "movie_ids": movie_ids,
            "http": http_status,
            "command_id": command_id,
        })

        log(
            f"     MoviesSearch movies={len(movie_ids)} "
            f"HTTP={http_status} commandId={command_id}"
        )

    write_report(report_path, targets, results)

    http_counts = Counter(str(result.get("delete_http")) for result in results.values())
    unlink_counts = Counter(str(result.get("unlink_status")) for result in results.values())
    summary["moviefiles_processed"] = len(results)
    summary["delete_http_counts"] = dict(http_counts)
    summary["unlink_counts"] = dict(unlink_counts)
    summary["refresh_count"] = len(refresh_results)
    summary["search_count"] = len(search_results)

    log("Résumé final")
    log(f"MovieFiles ciblés: {len(targets)}")
    log(f"MovieFiles traités API: {len(results)}")
    log(f"Films touchés: {len(affected_movies)}")
    log(f"RefreshMovie demandés: {len(refresh_results)}")
    log(f"MoviesSearch demandés: {len(search_results)}")
    log(f"HTTP suppressions: {dict(http_counts)}")
    log(f"Symlinks locaux: {dict(unlink_counts)}")
    log(f"Rapport écrit: {report_path}")

    queue_status, queue_body = api_request(
        "GET",
        config["RADARR_URL"],
        config["RADARR_API_KEY"],
        "queue",
    )

    if queue_status == 200 and isinstance(queue_body, dict):
        log(f"Queue Radarr totalRecords: {queue_body.get('totalRecords')}")
        summary["queue_total_records"] = queue_body.get("totalRecords")

    log("Terminé.")
    summary["status"] = "success"
    summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return 0, summary


def choose_menu(config):
    while True:
        print()
        print("Menu Radarr Cleanup")
        print("-------------------")
        print("1. Voir les réglages actuels")
        print("2. Modifier les réglages")
        print("3. Tester la connexion à Radarr")
        print("4. Simulation : détecter les fichiers cassés sans rien supprimer")
        print("5. Nettoyage : supprimer uniquement les fichiers cassés")
        print("6. Quitter")
        print()

        choice = input("Choix : ").strip()

        if choice == "1":
            print_config(config)
            continue

        if choice == "2":
            setup_config()
            config = load_config()
            continue

        if choice == "3":
            if ensure_config(config):
                test_api(config)
            continue

        if choice == "6":
            print("Fin.")
            sys.exit(0)

        if choice not in ["4", "5"]:
            print("Choix invalide.")
            continue

        if not ensure_config(config):
            continue

        apply = choice == "5"

        print()
        print("Options du traitement")
        print("---------------------")
        tag_ids = choose_tags_interactive(config)

        print()
        print("Limite de sécurité")
        print("------------------")
        print("Choisis combien de fichiers traiter au maximum pendant ce passage.")
        print("Conseil : commence par 20 pour vérifier le résultat.")
        print("Mets 0 uniquement si tu veux tout traiter d'un coup.")
        max_files = ask_int("Nombre maximum de fichiers à traiter", 20)

        print()
        print("Filtre par film")
        print("---------------")
        print("Tu peux limiter le nettoyage à un seul film.")
        print("Exemple : The Dark Knight")
        print("Laisse vide pour traiter tous les films.")
        movie_title = ask_text("Titre de film à cibler, vide = tous", "")

        print()
        print("Actions après nettoyage")
        print("-----------------------")
        print("Après suppression dans Radarr, le script peut aussi supprimer les anciens liens locaux cassés.")
        print("Recommandé : oui.")
        delete_local_symlinks = ask_yes_no("Supprimer les liens locaux cassés", True)

        print()
        print("Après suppression, Radarr peut rafraîchir les films concernés.")
        print("Recommandé : oui.")
        run_rescan = ask_yes_no("Lancer RefreshMovie après nettoyage", True)

        print()
        print("Après le refresh, Radarr peut rechercher automatiquement les films manquants.")
        print("Recommandé : oui.")
        run_search = ask_yes_no("Lancer MoviesSearch après nettoyage", True)

        keep_symlinks = not delete_local_symlinks
        skip_rescan = not run_rescan
        skip_search = not run_search

        if apply:
            print()
            print("ATTENTION : mode NETTOYAGE RÉEL.")
            print("Le script va supprimer dans Radarr les références aux MovieFiles sélectionnés.")
            print("Il ne traite que les fichiers locaux qui sont des liens vers le préfixe AllDebrid configuré.")
            print("Les vrais fichiers locaux hors AllDebrid ne sont pas ciblés.")
            confirm = input("Tape OUI pour confirmer le nettoyage : ").strip()

            if confirm != "OUI":
                print("Annulé.")
                continue

        execute_cleanup(
            config=config,
            apply=apply,
            max_files=max_files,
            tag_ids=tag_ids,
            movie_title=movie_title,
            keep_symlinks=keep_symlinks,
            skip_rescan=skip_rescan,
            skip_search=skip_search,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Nettoyage Radarr des symlinks cassés AllDebrid / Decypharr."
    )

    parser.add_argument("--setup", action="store_true", help="Créer ou modifier les réglages locaux.")
    parser.add_argument("--menu", action="store_true", help="Afficher le menu interactif.")
    parser.add_argument("--print-config", action="store_true", help="Afficher la configuration actuelle.")
    parser.add_argument("--test-api", action="store_true", help="Tester la connexion API Radarr.")

    parser.add_argument("--apply", action="store_true", help="Mode nettoyage réel : applique les suppressions dans Radarr.")
    parser.add_argument("--max-files", type=int, default=0, help="Nombre maximum de fichiers à traiter. 0 = tout traiter.")

    parser.add_argument("--library-root", action="append", default=[], help="Forcer un dossier racine Radarr à analyser. Option répétable.")
    parser.add_argument("--target-prefix", action="append", default=[], help="Forcer un préfixe AllDebrid/Decypharr à surveiller. Option répétable.")

    parser.add_argument("--tag-id", action="append", type=int, default=[], help="Limiter aux films ayant ce tag Radarr. Option répétable.")
    parser.add_argument("--movie-title", default="", help="Limiter aux films dont le titre contient ce texte.")

    parser.add_argument("--keep-symlinks", action="store_true", help="Conserver les liens locaux cassés après suppression dans Radarr.")
    parser.add_argument("--skip-rescan", action="store_true", help="Ne pas lancer RefreshMovie après nettoyage.")
    parser.add_argument("--skip-search", action="store_true", help="Ne pas lancer MoviesSearch après nettoyage.")

    return parser.parse_args()


def execute_cleanup(config, **kwargs):
    summary = build_execution_summary(
        config=config,
        apply=kwargs.get("apply", False),
        max_files=kwargs.get("max_files", 0),
        tag_ids=kwargs.get("tag_ids") or [],
        movie_title=kwargs.get("movie_title", ""),
        keep_symlinks=kwargs.get("keep_symlinks", False),
        skip_rescan=kwargs.get("skip_rescan", False),
        skip_search=kwargs.get("skip_search", False),
    )

    try:
        exit_code, summary = run_cleanup(config=config, **kwargs)
    except Exception as error:
        summary["status"] = "error"
        summary["error"] = str(error)
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log(f"ERREUR: {error}")
        exit_code = 1

    notify_discord_summary(config, summary)

    return exit_code


def main():
    args = parse_args()
    config = load_config()

    if args.setup:
        setup_config()
        return 0

    if args.print_config:
        print_config(config)
        return 0

    if args.test_api:
        if not ensure_config(config):
            return 1
        return 0 if test_api(config) else 1

    if args.menu or len(sys.argv) == 1:
        choose_menu(config)
        return 0

    if not ensure_config(config):
        summary = build_execution_summary(config=config)
        summary["status"] = "error"
        summary["error"] = "Clé API Radarr absente. Lance d'abord --setup."
        summary["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notify_discord_summary(config, summary)
        return 1

    if args.library_root:
        config["RADARR_LIBRARY_ROOTS"] = args.library_root

    if args.target_prefix:
        config["RADARR_TARGET_PREFIXES"] = args.target_prefix

    return execute_cleanup(
        config=config,
        apply=args.apply,
        max_files=args.max_files,
        tag_ids=args.tag_id,
        movie_title=args.movie_title,
        keep_symlinks=args.keep_symlinks,
        skip_rescan=args.skip_rescan,
        skip_search=args.skip_search,
    )


if __name__ == "__main__":
    sys.exit(main())
