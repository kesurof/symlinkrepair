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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

# Configuration unique : JSON avec de vraies listes.
# Aucune compatibilité avec l'ancien sonarr_cleanup.env.
CONFIG_FILE = SCRIPT_DIR / "sonarr_cleanup.json"

DEFAULTS = {
    "SONARR_URL": "http://127.0.0.1:8989",
    "SONARR_API_KEY": "",
    "SONARR_CONTAINER": "sonarr",
    "SONARR_LIBRARY_ROOTS": ["/home/USER/Medias/Series"],
    "SONARR_TARGET_PREFIXES": ["/mnt/decypharr/alldebrid/"],
    "DISCORD_NOTIFICATIONS_ENABLED": False,
    "DISCORD_WEBHOOK_URL": "",
}

TMP_DB = "/tmp/sonarr_cleanup_fresh.db"
DISCORD_USER_AGENT = "sonarr-cleanup-broken-alldebrid/1.0"


def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def mask_secret(value):
    if not value:
        return "NON CONFIGURÉE"
    if len(value) <= 8:
        return "********"
    return value[:4] + "..." + value[-4:]


def parse_bool(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in ["1", "true", "yes", "y", "on", "oui", "o"]


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_path_list(value):
    """
    Nettoie une liste de chemins issue du fichier JSON.

    Le format attendu est strictement une liste JSON :
    [
      "/chemin/1",
      "/chemin/2"
    ]

    Aucun séparateur texte n'est accepté.
    """
    if value is None:
        return []

    if not isinstance(value, list):
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

    normalized["SONARR_URL"] = str(normalized.get("SONARR_URL", "")).strip()
    normalized["SONARR_API_KEY"] = str(normalized.get("SONARR_API_KEY", "")).strip()
    normalized["SONARR_CONTAINER"] = str(normalized.get("SONARR_CONTAINER", "")).strip()
    normalized["DISCORD_WEBHOOK_URL"] = str(normalized.get("DISCORD_WEBHOOK_URL", "")).strip()
    normalized["DISCORD_NOTIFICATIONS_ENABLED"] = parse_bool(
        normalized.get("DISCORD_NOTIFICATIONS_ENABLED", False)
    )

    normalized["SONARR_LIBRARY_ROOTS"] = clean_path_list(
        normalized.get("SONARR_LIBRARY_ROOTS", [])
    )

    normalized["SONARR_TARGET_PREFIXES"] = clean_prefix_list(
        normalized.get("SONARR_TARGET_PREFIXES", [])
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
            else:
                log(f"AVERTISSEMENT: le fichier {CONFIG_FILE} ne contient pas un objet JSON.")
        except json.JSONDecodeError as error:
            log(f"AVERTISSEMENT: configuration JSON illisible: {CONFIG_FILE} | {error}")

    # Variables d'environnement acceptées uniquement pour les valeurs simples.
    # Les listes de chemins doivent être dans sonarr_cleanup.json ou passées en options CLI.
    for key in [
        "SONARR_URL",
        "SONARR_API_KEY",
        "SONARR_CONTAINER",
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


def prompt_scalar_setting(key, label, current_value, secret=False):
    if secret:
        shown = mask_secret(current_value)
    else:
        shown = current_value

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
    print("Configuration Sonarr")
    print("--------------------")
    print("Laisse vide pour garder la valeur actuelle.")
    print("Les chemins multiples se saisissent maintenant un par un.")
    print("Plus besoin de les séparer avec un caractère spécial.")
    print()

    new_config = {}

    new_config["SONARR_URL"] = prompt_scalar_setting(
        "SONARR_URL",
        "Adresse de Sonarr",
        current.get("SONARR_URL", DEFAULTS["SONARR_URL"]),
    )

    new_config["SONARR_API_KEY"] = prompt_scalar_setting(
        "SONARR_API_KEY",
        "Clé API Sonarr",
        current.get("SONARR_API_KEY", ""),
        secret=True,
    )

    new_config["SONARR_CONTAINER"] = prompt_scalar_setting(
        "SONARR_CONTAINER",
        "Nom du conteneur Docker Sonarr",
        current.get("SONARR_CONTAINER", DEFAULTS["SONARR_CONTAINER"]),
    )

    new_config["SONARR_LIBRARY_ROOTS"] = prompt_path_list(
        "Dossiers racines des séries à analyser",
        current.get("SONARR_LIBRARY_ROOTS", []),
        "/home/USER/Medias/Series",
    )

    new_config["SONARR_TARGET_PREFIXES"] = prompt_path_list(
        "Préfixes des liens AllDebrid / Decypharr à surveiller",
        current.get("SONARR_TARGET_PREFIXES", []),
        "/mnt/decypharrsonarr/alldebrid/",
    )

    print()
    print("Notifications Discord")
    print("---------------------")
    new_config["DISCORD_NOTIFICATIONS_ENABLED"] = ask_yes_no(
        "Activer les notifications Discord",
        current.get("DISCORD_NOTIFICATIONS_ENABLED", False),
    )
    new_config["DISCORD_WEBHOOK_URL"] = prompt_scalar_setting(
        "DISCORD_WEBHOOK_URL",
        "URL du webhook Discord",
        current.get("DISCORD_WEBHOOK_URL", ""),
        secret=True,
    )

    save_config(new_config)

    print()
    print("Configuration terminée.")
    print(f"Nouveau fichier de configuration : {CONFIG_FILE}")

    print()
    print("Tu peux maintenant lancer :")
    print("./sonarr_cleanup_broken_alldebrid.py")
    print()

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
        raise RuntimeError(f"Impossible de joindre Sonarr: {error}") from error


def ensure_config(config):
    if not config.get("SONARR_API_KEY"):
        print()
        print("ERREUR : clé API Sonarr absente.")
        print("Lance d'abord :")
        print("./sonarr_cleanup_broken_alldebrid.py --setup")
        print()
        return False

    return True


def print_config(config):
    print()
    print("Configuration actuelle")
    print("----------------------")
    print(f"SONARR_URL             = {config['SONARR_URL']}")
    print(f"SONARR_API_KEY         = {mask_secret(config['SONARR_API_KEY'])}")
    print(f"SONARR_CONTAINER       = {config['SONARR_CONTAINER']}")
    print(f"SONARR_LIBRARY_ROOTS   = {clean_path_list(config.get('SONARR_LIBRARY_ROOTS'))}")
    print(f"SONARR_TARGET_PREFIXES = {clean_prefix_list(config.get('SONARR_TARGET_PREFIXES'))}")
    print(f"DISCORD_ENABLED        = {config.get('DISCORD_NOTIFICATIONS_ENABLED', False)}")
    print(f"DISCORD_WEBHOOK_URL    = {mask_secret(config.get('DISCORD_WEBHOOK_URL', ''))}")
    print(f"CONFIG_FILE            = {CONFIG_FILE}")

    roots = clean_path_list(config.get("SONARR_LIBRARY_ROOTS"))
    prefixes = clean_prefix_list(config.get("SONARR_TARGET_PREFIXES"))

    print()
    print("Dossiers Sonarr analysés :")
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
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
        "system/status",
    )

    if status != 200:
        print(f"ERREUR API Sonarr HTTP={status}")
        print(body)
        return False

    print()
    print("API Sonarr OK")
    print(f"Version : {body.get('version')}")
    print(f"AppData : {body.get('appData')}")
    print()

    return True


def get_tags(config):
    status, body = api_request(
        "GET",
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
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


def choose_tags_interactive(config):
    tags = get_tags(config)

    print()
    print("Filtre par tags Sonarr")
    print("----------------------")
    print("Un tag est une étiquette ajoutée dans Sonarr, par exemple : huntarr-missing.")
    print("Laisse vide pour traiter toutes les séries, sans filtre par tag.")

    if not tags:
        print()
        print("Aucun tag récupéré depuis Sonarr.")
        value = input("Tags à utiliser, vide = toutes les séries : ").strip()
        return parse_int_list(value)

    print()
    print("Tags disponibles :")
    for tag in tags:
        print(f"  {tag['id']:>4}  {tag['label']}")

    print()
    print("Entre le ou les IDs de tags à utiliser, séparés par une virgule.")
    print("Exemple : 6 ou 6,8,12")
    value = input("Tags à utiliser, vide = toutes les séries : ").strip()

    return parse_int_list(value)


def parse_int_list(value):
    if not value:
        return []

    result = []

    for part in value.split(","):
        part = part.strip()

        if part.isdigit():
            result.append(int(part))

    return sorted(set(result))


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


def choose_menu(config):
    while True:
        print()
        print("Menu Sonarr Cleanup")
        print("-------------------")
        print("1. Voir les réglages actuels")
        print("2. Modifier les réglages")
        print("3. Tester la connexion à Sonarr")
        print("4. Simulation : détecter les fichiers cassés sans rien supprimer")
        print("5. Nettoyage : supprimer uniquement les fichiers cassés")
        print("6. Simulation : nettoyer toute la saison si au moins un épisode est cassé")
        print("7. Nettoyage : supprimer toute la saison si au moins un épisode est cassé")
        print("8. Quitter")
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

        if choice == "8":
            print("Fin.")
            sys.exit(0)

        if choice not in ["4", "5", "6", "7"]:
            print("Choix invalide.")
            continue

        if not ensure_config(config):
            continue

        apply = choice in ["5", "7"]
        delete_season = choice in ["6", "7"]

        print()
        print("Options du traitement")
        print("---------------------")
        tag_ids = choose_tags_interactive(config)

        print()
        print("Limite de sécurité")
        print("------------------")
        if delete_season:
            print("Choisis une limite de traitement pour ce passage.")
            print("Important : en mode saison entière, le script ne coupe jamais une saison en deux.")
            print("Il peut donc traiter un peu moins que la limite, ou un peu plus si la première saison dépasse déjà la limite.")
            print("Conseil : commence par 20 ou 50 pour vérifier le résultat.")
            print("Mets 0 uniquement si tu veux tout traiter d'un coup.")
            max_files = ask_int("Limite de fichiers pour ce passage", 20)
        else:
            print("Choisis combien de fichiers traiter au maximum pendant ce passage.")
            print("Conseil : commence par 20 pour vérifier le résultat.")
            print("Mets 0 uniquement si tu veux tout traiter d'un coup.")
            max_files = ask_int("Nombre maximum de fichiers à traiter", 20)

        print()
        print("Filtre par série")
        print("----------------")
        print("Tu peux limiter le nettoyage à une seule série.")
        print("Exemple : Zero Day")
        print("Laisse vide pour traiter toutes les séries.")
        series_title = ask_text("Titre de série à cibler, vide = toutes", "")

        print()
        print("Filtre par saison")
        print("-----------------")
        print("Tu peux limiter le nettoyage à une seule saison.")
        print("Exemple : 2 pour la saison 2.")
        print("Mets 0 pour traiter toutes les saisons.")
        season = ask_int("Saison à cibler, 0 = toutes", 0)

        print()
        print("Actions après nettoyage")
        print("-----------------------")
        print("Après suppression dans Sonarr, le script peut aussi supprimer les anciens liens locaux cassés.")
        print("Recommandé : oui, pour nettoyer les raccourcis inutiles.")
        delete_local_symlinks = ask_yes_no("Supprimer les liens locaux cassés", True)

        print()
        print("Après suppression, Sonarr peut rescanner uniquement les séries concernées.")
        print("Recommandé : oui.")
        run_rescan = ask_yes_no("Lancer le scan ciblé après nettoyage", True)

        print()
        print("Après le scan, Sonarr peut rechercher automatiquement les saisons/épisodes manquants.")
        print("Recommandé : oui.")
        run_search = ask_yes_no("Lancer la recherche automatique après nettoyage", True)

        keep_symlinks = not delete_local_symlinks
        skip_rescan = not run_rescan
        skip_search = not run_search

        if apply:
            print()
            print("ATTENTION : mode NETTOYAGE RÉEL.")
            print("Le script va supprimer dans Sonarr les références aux fichiers sélectionnés.")
            print("Il ne traite que les fichiers locaux qui sont des liens vers le préfixe AllDebrid configuré.")
            print("Les vrais fichiers locaux hors AllDebrid ne sont pas ciblés.")
            confirm = input("Tape OUI pour confirmer le nettoyage : ").strip()

            if confirm != "OUI":
                print("Annulé.")
                continue

        execute_cleanup(
            config=config,
            apply=apply,
            delete_season=delete_season,
            max_files=max_files,
            tag_ids=tag_ids,
            series_title=series_title,
            season=season if season > 0 else None,
            keep_symlinks=keep_symlinks,
            skip_rescan=skip_rescan,
            skip_search=skip_search,
        )


def copy_fresh_db(container, db_path):
    if os.path.exists(db_path):
        os.remove(db_path)

    log(f"Copie DB fraîche : {container}:/config/sonarr.db -> {db_path}")

    run_cmd([
        "docker",
        "cp",
        f"{container}:/config/sonarr.db",
        db_path,
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


def load_sonarr_records(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row

    rows = connection.execute("""
        SELECT
            ef.Id AS episode_file_id,
            ef.SeriesId AS series_id,
            ef.SeasonNumber AS episode_file_season,
            ef.RelativePath AS relative_path,
            ef.Size AS size,
            s.Title AS series_title,
            s.Path AS series_path,
            s.Tags AS series_tags,
            GROUP_CONCAT(e.Id) AS episode_ids,
            GROUP_CONCAT(e.SeasonNumber) AS episode_seasons,
            GROUP_CONCAT(e.EpisodeNumber) AS episode_numbers
        FROM EpisodeFiles ef
        JOIN Series s ON s.Id = ef.SeriesId
        LEFT JOIN Episodes e ON e.EpisodeFileId = ef.Id
        GROUP BY ef.Id
    """).fetchall()

    connection.close()

    records = []
    records_by_path = {}

    for row in rows:
        series_path = row["series_path"]
        relative_path = row["relative_path"]

        if not series_path or not relative_path:
            continue

        full_path = f"{series_path.rstrip('/')}/{relative_path.lstrip('/')}"

        episode_ids = []
        if row["episode_ids"]:
            episode_ids = [
                int(value)
                for value in str(row["episode_ids"]).split(",")
                if value.strip().isdigit()
            ]

        episode_numbers = []
        if row["episode_numbers"]:
            episode_numbers = [
                int(value)
                for value in str(row["episode_numbers"]).split(",")
                if value.strip().isdigit()
            ]

        series_tags = [
            int(value)
            for value in parse_json_array(row["series_tags"])
            if str(value).isdigit()
        ]

        record = {
            "episode_file_id": int(row["episode_file_id"]),
            "series_id": int(row["series_id"]),
            "series_title": row["series_title"],
            "series_tags": sorted(set(series_tags)),
            "season_number": int(row["episode_file_season"]),
            "relative_path": relative_path,
            "full_path": full_path,
            "size": int(row["size"] or 0),
            "episode_ids": episode_ids,
            "episode_numbers": episode_numbers,
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

    for root in roots:
        root_path = Path(root)

        if not root_path.is_dir():
            log(f"SKIP chemin Sonarr introuvable : {root}")
            continue

        for path in iter_symlinks(root):
            info = symlink_info(path, target_prefixes)

            if info["target_matches"] and info["broken"]:
                broken[path] = info

    return broken


def record_matches_filters(record, tag_ids=None, series_title="", season=None):
    tag_ids = tag_ids or []

    if tag_ids:
        if not set(tag_ids).intersection(set(record["series_tags"])):
            return False

    if series_title:
        if series_title.lower() not in record["series_title"].lower():
            return False

    if season is not None:
        if record["season_number"] != season:
            return False

    return True


def choose_targets(records, records_by_path, broken_symlinks, target_prefixes, delete_season, tag_ids, series_title, season):
    broken_records = []

    for path, info in broken_symlinks.items():
        record = records_by_path.get(path)

        if not record:
            continue

        if not record_matches_filters(record, tag_ids, series_title, season):
            continue

        broken_records.append({
            **record,
            "symlink_target": info["target"],
            "reason": "broken_symlink",
        })

    if not delete_season:
        return unique_targets(broken_records), unique_targets(broken_records)

    affected_seasons = {
        (record["series_id"], record["season_number"])
        for record in broken_records
    }

    season_targets = []

    for record in records:
        key = (record["series_id"], record["season_number"])

        if key not in affected_seasons:
            continue

        if not record_matches_filters(record, tag_ids, series_title, season):
            continue

        info = symlink_info(record["full_path"], target_prefixes)

        if not info["is_symlink"]:
            continue

        if not info["target_matches"]:
            continue

        reason = "season_delete_existing_symlink"

        if info["broken"]:
            reason = "season_delete_broken_symlink"

        season_targets.append({
            **record,
            "symlink_target": info["target"],
            "reason": reason,
        })

    return unique_targets(season_targets), unique_targets(broken_records)


def unique_targets(targets):
    seen = set()
    result = []

    for target in targets:
        episode_file_id = target["episode_file_id"]

        if episode_file_id in seen:
            continue

        seen.add(episode_file_id)
        result.append(target)

    return result


def apply_max_files_limit(targets, max_files, delete_season):
    """
    Applique la limite de traitement.

    Mode normal :
      - limite simple au nombre de fichiers demandé.

    Mode --delete-season :
      - ne coupe jamais au milieu d'une saison.
      - les cibles sont regroupées par série + saison.
      - si le prochain groupe complet dépasse la limite, il est reporté au prochain passage.
      - si le premier groupe dépasse déjà la limite, il est pris en entier pour éviter de bloquer.
    """
    if not max_files or max_files <= 0:
        return targets, False, []

    if not delete_season:
        return targets[:max_files], len(targets) > max_files, []

    grouped = []
    current_key = None
    current_group = []

    for target in targets:
        key = (
            target["series_id"],
            target["series_title"],
            target["season_number"],
        )

        if current_key is None:
            current_key = key

        if key != current_key:
            grouped.append((current_key, current_group))
            current_key = key
            current_group = []

        current_group.append(target)

    if current_group:
        grouped.append((current_key, current_group))

    selected = []
    deferred_groups = []

    for key, group in grouped:
        would_exceed = len(selected) + len(group) > max_files

        if would_exceed and selected:
            deferred_groups.append((key, len(group)))
            continue

        if would_exceed and not selected:
            # La première saison dépasse la limite.
            # On la garde entière, sinon elle ne pourrait jamais être traitée.
            selected.extend(group)
            continue

        selected.extend(group)

    truncated = len(selected) < len(targets)

    return selected, truncated, deferred_groups


def delete_episode_file(config, episode_file_id):
    return api_request(
        "DELETE",
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
        f"episodefile/{episode_file_id}",
    )


def post_command(config, payload):
    return api_request(
        "POST",
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
        "command",
        payload=payload,
    )


def build_execution_summary(config, **kwargs):
    return {
        "started_at": utc_timestamp(),
        "finished_at": "",
        "status": "running",
        "mode": "apply" if kwargs.get("apply") else "dry_run",
        "report_path": "",
        "error": "",
        "config": {
            "sonarr_url": config.get("SONARR_URL", ""),
            "library_roots": clean_path_list(config.get("SONARR_LIBRARY_ROOTS")),
            "target_prefixes": clean_prefix_list(config.get("SONARR_TARGET_PREFIXES")),
        },
        "filters": {
            "tag_ids": list(kwargs.get("tag_ids") or []),
            "series_title": kwargs.get("series_title", ""),
            "season": kwargs.get("season"),
            "delete_season": bool(kwargs.get("delete_season")),
            "max_files": int(kwargs.get("max_files") or 0),
            "keep_symlinks": bool(kwargs.get("keep_symlinks")),
            "skip_rescan": bool(kwargs.get("skip_rescan")),
            "skip_search": bool(kwargs.get("skip_search")),
        },
        "stats": {
            "existing_roots": [],
            "missing_roots": [],
            "episode_files_db": 0,
            "broken_symlinks": 0,
            "broken_records": 0,
            "targets_before_limit": 0,
            "targets_selected": 0,
            "series_affected": 0,
            "seasons_affected": 0,
            "episode_ids_affected": 0,
            "max_limit_applied": False,
            "deferred_groups": 0,
            "reason_counts": {},
            "api_deletions": 0,
            "rescans_requested": 0,
            "searches_requested": 0,
            "queue_total_records": None,
            "delete_http_counts": {},
            "unlink_counts": {},
        },
    }


def format_counter_lines(counter_dict):
    if not counter_dict:
        return "-"

    return "\n".join(
        f"`{key}`: **{value}**"
        for key, value in sorted(counter_dict.items())
    )


def truncate_text(value, limit=1000):
    value = str(value or "").strip()

    if len(value) <= limit:
        return value or "-"

    return value[: limit - 3] + "..."


def build_discord_payload(summary):
    stats = summary["stats"]
    filters = summary["filters"]
    is_error = summary["status"] == "error"
    is_apply = summary["mode"] == "apply"
    has_actions = stats["api_deletions"] or stats["rescans_requested"] or stats["searches_requested"]

    if is_error:
        color = 0xED4245
        title = "🔴 Sonarr Cleanup | Erreur"
        description = "Echec du script de maintenance Sonarr."
    elif is_apply and has_actions:
        color = 0xF1C40F
        title = "🟡 Sonarr Cleanup | Nettoyage"
        description = "Nettoyage termine avec actions Sonarr lancees."
    elif is_apply:
        color = 0x57F287
        title = "🟢 Sonarr Cleanup | Nettoyage"
        description = "Nettoyage termine sans erreur."
    else:
        color = 0x57F287
        title = "🟢 Sonarr Cleanup | Simulation"
        description = "Execution terminee sans erreur."

    fields = [
        {
            "name": "🧭 Vue d'ensemble",
            "value": (
                f"**Statut**: **{'✅ success' if summary['status'] == 'success' else '❌ error'}**\n"
                f"**Mode**: **{summary['mode']}**\n"
                f"**Début**: `{summary['started_at']}`\n"
                f"**Fin**: `{summary['finished_at']}`"
            ),
            "inline": False,
        },
        {
            "name": "🔎 Détection",
            "value": (
                f"**DB EpisodeFiles**: **{stats['episode_files_db']}**\n"
                f"**Symlinks cassés**: **{stats['broken_symlinks']}**\n"
                f"**Records matchés**: **{stats['broken_records']}**"
            ),
            "inline": True,
        },
        {
            "name": "🎯 Ciblage",
            "value": (
                f"**Avant limite**: **{stats['targets_before_limit']}**\n"
                f"**Sélectionnés**: **{stats['targets_selected']}**\n"
                f"**Séries/Saisons**: **{stats['series_affected']}**/**{stats['seasons_affected']}**"
            ),
            "inline": True,
        },
        {
            "name": "🛠️ Actions",
            "value": (
                f"**Suppressions API**: **{stats['api_deletions']}**\n"
                f"**Rescans**: **{stats['rescans_requested']}**\n"
                f"**Recherches**: **{stats['searches_requested']}**"
            ),
            "inline": True,
        },
        {
            "name": "📊 Comptages",
            "value": (
                f"**Raisons**\n{format_counter_lines(stats['reason_counts'])}\n\n"
                f"**HTTP suppressions**\n{format_counter_lines(stats['delete_http_counts'])}\n\n"
                f"**Symlinks locaux**\n{format_counter_lines(stats['unlink_counts'])}"
            ),
            "inline": False,
        },
        {
            "name": "🧪 Filtres",
            "value": (
                f"**Tags**: `{filters['tag_ids'] or 'tous'}`\n"
                f"**Série**: `{filters['series_title'] or 'toutes'}`\n"
                f"**Saison**: `{filters['season'] if filters['season'] is not None else 'toutes'}`\n"
                f"**delete_season**: `{filters['delete_season']}` | **max_files**: `{filters['max_files'] or 'illimite'}`"
            ),
            "inline": False,
        },
    ]

    if summary.get("report_path"):
        fields.append({
            "name": "📝 Rapport",
            "value": f"`{truncate_text(summary['report_path'], 1000)}`",
            "inline": False,
        })

    if stats["missing_roots"]:
        fields.append({
            "name": "⚠️ Chemins ignorés",
            "value": truncate_text("\n".join(f"`{root}`" for root in stats["missing_roots"])),
            "inline": False,
        })

    if summary.get("error"):
        fields.append({
            "name": "🚨 Erreur",
            "value": f"```\n{truncate_text(summary['error'], 900)}\n```",
            "inline": False,
        })

    return {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {
                "text": "sonarr_cleanup_broken_alldebrid",
            },
            "timestamp": summary["finished_at"],
        }],
    }


def send_discord_webhook(config, summary):
    if not config.get("DISCORD_NOTIFICATIONS_ENABLED"):
        return False

    webhook_url = str(config.get("DISCORD_WEBHOOK_URL", "")).strip()

    if not webhook_url:
        log("AVERTISSEMENT: notifications Discord activées mais webhook absent.")
        return False

    payload = build_discord_payload(summary)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": DISCORD_USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in [200, 204]:
                raise RuntimeError(f"HTTP={response.status}")

        log("Notification Discord envoyée.")
        return True
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        log(f"AVERTISSEMENT: échec notification Discord HTTP={error.code} body={raw}")
    except urllib.error.URLError as error:
        log(f"AVERTISSEMENT: échec notification Discord: {error}")
    except Exception as error:
        log(f"AVERTISSEMENT: échec notification Discord: {error}")

    return False


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
            "episodeFileId\tepisodeIds\tseriesId\tseriesTitle\tseriesTags\tseason\t"
            "fullPath\tsymlinkTarget\treason\tdeleteHttp\tunlinkStatus\n"
        )

        for target in targets:
            episode_file_id = target["episode_file_id"]
            result = results.get(episode_file_id, {})

            file.write(
                f"{episode_file_id}\t"
                f"{','.join(map(str, target['episode_ids']))}\t"
                f"{target['series_id']}\t"
                f"{target['series_title']}\t"
                f"{','.join(map(str, target['series_tags']))}\t"
                f"{target['season_number']}\t"
                f"{target['full_path']}\t"
                f"{target.get('symlink_target', '')}\t"
                f"{target.get('reason', '')}\t"
                f"{result.get('delete_http', '')}\t"
                f"{result.get('unlink_status', '')}\n"
            )


def run_cleanup(
    config,
    apply=False,
    delete_season=False,
    max_files=0,
    tag_ids=None,
    series_title="",
    season=None,
    keep_symlinks=False,
    skip_rescan=False,
    skip_search=False,
    summary=None,
):
    tag_ids = tag_ids or []
    dry_run = not apply

    started_at = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"/tmp/sonarr_cleanup_report_{started_at}.tsv"

    if summary is not None:
        summary["report_path"] = report_path

    log("Démarrage traitement")
    log(f"Mode: {'NETTOYAGE RÉEL' if apply else 'SIMULATION'}")
    log(f"Suppression saison entière: {'oui' if delete_season else 'non'}")
    log(f"Max files: {'illimité' if max_files == 0 else max_files}")
    log(f"Tags inclus: {tag_ids if tag_ids else 'tous'}")
    log(f"Filtre titre: {series_title if series_title else 'aucun'}")
    log(f"Filtre saison: {season if season is not None else 'toutes'}")

    library_roots = clean_path_list(config.get("SONARR_LIBRARY_ROOTS"))
    target_prefixes = clean_prefix_list(config.get("SONARR_TARGET_PREFIXES"))

    existing_roots = [root for root in library_roots if Path(root).is_dir()]
    missing_roots = [root for root in library_roots if not Path(root).is_dir()]

    if summary is not None:
        summary["stats"]["existing_roots"] = existing_roots
        summary["stats"]["missing_roots"] = missing_roots

    if missing_roots:
        for root in missing_roots:
            log(f"AVERTISSEMENT: chemin Sonarr introuvable, ignoré: {root}")

    if not existing_roots:
        log("ERREUR: aucun dossier racine Sonarr valide à analyser.")
        log("Corrige SONARR_LIBRARY_ROOTS avec --setup.")
        return 1

    if not target_prefixes:
        log("ERREUR: aucun préfixe AllDebrid / Decypharr configuré.")
        log("Corrige SONARR_TARGET_PREFIXES avec --setup.")
        return 1

    log(f"Dossiers Sonarr analysés: {existing_roots}")
    log(f"Préfixes de symlinks surveillés: {target_prefixes}")

    status, body = api_request(
        "GET",
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
        "system/status",
    )

    if status != 200:
        log(f"ERREUR API Sonarr HTTP={status}")
        print(body)
        return 1

    log(f"Sonarr OK version={body.get('version')}")

    copy_fresh_db(config["SONARR_CONTAINER"], TMP_DB)

    records, records_by_path = load_sonarr_records(TMP_DB)
    log(f"EpisodeFiles chargés depuis DB: {len(records)}")

    if summary is not None:
        summary["stats"]["episode_files_db"] = len(records)

    broken_symlinks = collect_broken_symlinks(
        existing_roots,
        target_prefixes,
    )
    log(f"Symlinks cassés vers AllDebrid détectés: {len(broken_symlinks)}")

    if summary is not None:
        summary["stats"]["broken_symlinks"] = len(broken_symlinks)

    targets, broken_records = choose_targets(
        records=records,
        records_by_path=records_by_path,
        broken_symlinks=broken_symlinks,
        target_prefixes=target_prefixes,
        delete_season=delete_season,
        tag_ids=tag_ids,
        series_title=series_title,
        season=season,
    )

    total_targets_before_limit = len(targets)

    targets, max_limit_applied, deferred_groups = apply_max_files_limit(
        targets=targets,
        max_files=max_files,
        delete_season=delete_season,
    )

    if max_files and max_files > 0:
        if delete_season:
            log(
                "Limite appliquée sans couper de saison: "
                f"{len(targets)}/{total_targets_before_limit} EpisodeFiles sélectionnés"
            )

            if len(targets) > max_files:
                log(
                    "AVERTISSEMENT: la première saison sélectionnée dépasse la limite demandée. "
                    f"Le script traite {len(targets)} fichiers pour ne pas couper la saison."
                )

            if deferred_groups:
                log("Groupes complets reportés au prochain passage:")
                for (series_id, series_title, season_number), group_size in deferred_groups[:20]:
                    log(
                        f"  - SID={series_id} {series_title} "
                        f"S{season_number:02d} : {group_size} fichiers"
                    )

                if len(deferred_groups) > 20:
                    log(f"  ... {len(deferred_groups) - 20} autres groupes reportés")
        elif max_limit_applied:
            log(
                "Limite appliquée: "
                f"{len(targets)}/{total_targets_before_limit} EpisodeFiles sélectionnés"
            )

    affected_series = sorted({
        (target["series_id"], target["series_title"])
        for target in targets
    })

    affected_seasons = sorted({
        (target["series_id"], target["series_title"], target["season_number"])
        for target in targets
    })

    affected_episode_ids = sorted({
        episode_id
        for target in targets
        for episode_id in target["episode_ids"]
    })

    reason_counts = Counter(target["reason"] for target in targets)

    if summary is not None:
        summary["stats"].update({
            "broken_records": len(broken_records),
            "targets_before_limit": total_targets_before_limit,
            "targets_selected": len(targets),
            "series_affected": len(affected_series),
            "seasons_affected": len(affected_seasons),
            "episode_ids_affected": len(affected_episode_ids),
            "max_limit_applied": max_limit_applied,
            "deferred_groups": len(deferred_groups),
            "reason_counts": dict(reason_counts),
        })

    log("Résumé avant action")
    log(f"Broken records Sonarr matchés: {len(broken_records)}")
    log(f"EpisodeFiles à traiter: {len(targets)}")
    log(f"Séries touchées: {len(affected_series)}")
    log(f"Saisons touchées: {len(affected_seasons)}")
    log(f"EpisodeIds concernés: {len(affected_episode_ids)}")
    log(f"Raisons: {dict(reason_counts)}")
    log(f"Rapport prévu: {report_path}")

    if not targets:
        log("Aucune cible à traiter.")
        write_report(report_path, [], {})
        log(f"Rapport écrit: {report_path}")
        return 0

    print()
    print("Aperçu limité des 20 premières cibles")
    print("--------------------------------------")

    for target in targets[:20]:
        print(
            f"EFID={target['episode_file_id']} "
            f"SID={target['series_id']} "
            f"S{target['season_number']:02d} "
            f"{target['series_title']} "
            f"reason={target['reason']}"
        )

    print()

    if dry_run:
        log("SIMULATION : aucune suppression, aucun scan, aucune recherche.")
        write_report(report_path, targets, {})
        log(f"Rapport écrit: {report_path}")
        return 0

    results = {}

    log("Suppression des EpisodeFiles Sonarr")

    for index, target in enumerate(targets, start=1):
        episode_file_id = target["episode_file_id"]
        full_path = target["full_path"]

        info = symlink_info(full_path, target_prefixes)

        if not info["is_symlink"]:
            log(f"[{index}/{len(targets)}] SKIP EFID={episode_file_id} not_symlink")
            continue

        if not info["target_matches"]:
            log(f"[{index}/{len(targets)}] SKIP EFID={episode_file_id} target_not_allowed")
            continue

        if not delete_season and not info["broken"]:
            log(f"[{index}/{len(targets)}] SKIP EFID={episode_file_id} not_broken")
            continue

        log(
            f"[{index}/{len(targets)}] DELETE EFID={episode_file_id} "
            f"{target['series_title']} S{target['season_number']:02d}"
        )

        http_status, response_body = delete_episode_file(config, episode_file_id)

        unlink_status = "kept"

        if not keep_symlinks:
            unlink_status = unlink_symlink_if_allowed(
                full_path,
                target_prefixes,
            )

        results[episode_file_id] = {
            "delete_http": http_status,
            "delete_body": response_body,
            "unlink_status": unlink_status,
        }

        log(f"     HTTP={http_status} unlink={unlink_status}")

        time.sleep(0.05)

    scan_results = []

    if not skip_rescan:
        log("Scan ciblé des séries touchées")

        for series_id, series_title in affected_series:
            payload = {
                "name": "RescanSeries",
                "seriesId": series_id,
            }

            http_status, body = post_command(config, payload)
            command_id = body.get("id") if isinstance(body, dict) else None

            scan_results.append({
                "series_id": series_id,
                "series_title": series_title,
                "http": http_status,
                "command_id": command_id,
            })

            log(
                f"     RescanSeries SID={series_id} "
                f"{series_title} HTTP={http_status} commandId={command_id}"
            )

            time.sleep(0.10)

    search_results = []

    if not skip_search:
        log("Recherche par saison touchée")

        for series_id, series_title, season_number in affected_seasons:
            payload = {
                "name": "SeasonSearch",
                "seriesId": series_id,
                "seasonNumber": season_number,
            }

            http_status, body = post_command(config, payload)
            command_id = body.get("id") if isinstance(body, dict) else None

            search_results.append({
                "series_id": series_id,
                "series_title": series_title,
                "season_number": season_number,
                "http": http_status,
                "command_id": command_id,
            })

            log(
                f"     SeasonSearch SID={series_id} "
                f"S{season_number:02d} {series_title} "
                f"HTTP={http_status} commandId={command_id}"
            )

            time.sleep(0.10)

    write_report(report_path, targets, results)

    http_counts = Counter(str(result.get("delete_http")) for result in results.values())
    unlink_counts = Counter(str(result.get("unlink_status")) for result in results.values())

    if summary is not None:
        summary["stats"].update({
            "api_deletions": len(results),
            "rescans_requested": len(scan_results),
            "searches_requested": len(search_results),
            "delete_http_counts": dict(http_counts),
            "unlink_counts": dict(unlink_counts),
        })

    log("Résumé final")
    log(f"EpisodeFiles ciblés: {len(targets)}")
    log(f"EpisodeFiles traités API: {len(results)}")
    log(f"Séries touchées: {len(affected_series)}")
    log(f"Saisons touchées: {len(affected_seasons)}")
    log(f"Scans demandés: {len(scan_results)}")
    log(f"Recherches saison demandées: {len(search_results)}")
    log(f"HTTP suppressions: {dict(http_counts)}")
    log(f"Symlinks locaux: {dict(unlink_counts)}")
    log(f"Rapport écrit: {report_path}")

    queue_status, queue_body = api_request(
        "GET",
        config["SONARR_URL"],
        config["SONARR_API_KEY"],
        "queue",
    )

    if queue_status == 200 and isinstance(queue_body, dict):
        log(f"Queue Sonarr totalRecords: {queue_body.get('totalRecords')}")

        if summary is not None:
            summary["stats"]["queue_total_records"] = queue_body.get("totalRecords")

    log("Terminé.")
    return 0


def execute_cleanup(config, **kwargs):
    summary = build_execution_summary(config, **kwargs)
    exit_code = 1

    try:
        exit_code = run_cleanup(config=config, summary=summary, **kwargs)
        summary["status"] = "success" if exit_code == 0 else "error"
    except Exception as error:
        summary["status"] = "error"
        summary["error"] = str(error)
        log(f"ERREUR: {error}")
    finally:
        summary["finished_at"] = utc_timestamp()

        if not summary.get("error") and summary["status"] == "error":
            summary["error"] = "Le script s'est terminé avec un code non nul."

        send_discord_webhook(config, summary)

    return exit_code


def parse_args():
    parser = argparse.ArgumentParser(
        description="Nettoyage Sonarr des symlinks cassés AllDebrid / Decypharr."
    )

    parser.add_argument("--setup", action="store_true", help="Créer ou modifier les réglages locaux.")
    parser.add_argument("--menu", action="store_true", help="Afficher le menu interactif.")

    parser.add_argument("--apply", action="store_true", help="Mode nettoyage réel : applique les suppressions dans Sonarr.")
    parser.add_argument("--delete-season", action="store_true", help="Si une saison contient un fichier cassé, nettoyer toute la saison concernée.")
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help=(
            "Nombre maximum de fichiers à traiter. 0 = tout traiter. "
            "Avec --delete-season, la limite ne coupe jamais une saison en deux."
        ),
    )
    parser.add_argument("--library-root", action="append", default=[], help="Forcer un dossier racine Sonarr à analyser. Option répétable.")
    parser.add_argument("--target-prefix", action="append", default=[], help="Forcer un préfixe AllDebrid/Decypharr à surveiller. Option répétable.")

    parser.add_argument("--tag-id", action="append", type=int, default=[], help="Limiter aux séries ayant ce tag Sonarr. Option répétable.")
    parser.add_argument("--series-title", default="", help="Limiter aux séries dont le titre contient ce texte.")
    parser.add_argument("--season", type=int, default=0, help="Limiter à une saison précise. 0 = toutes les saisons.")

    parser.add_argument("--keep-symlinks", action="store_true", help="Conserver les liens locaux cassés après suppression dans Sonarr.")
    parser.add_argument("--skip-rescan", action="store_true", help="Ne pas lancer le scan ciblé Sonarr après nettoyage.")
    parser.add_argument("--skip-search", action="store_true", help="Ne pas lancer la recherche automatique Sonarr après nettoyage.")

    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()

    if args.setup:
        setup_config()
        return 0

    if args.menu or len(sys.argv) == 1:
        choose_menu(config)
        return 0

    if not ensure_config(config):
        return 1

    if args.library_root:
        config["SONARR_LIBRARY_ROOTS"] = args.library_root

    if args.target_prefix:
        config["SONARR_TARGET_PREFIXES"] = args.target_prefix

    season = args.season if args.season > 0 else None

    return execute_cleanup(
        config=config,
        apply=args.apply,
        delete_season=args.delete_season,
        max_files=args.max_files,
        tag_ids=args.tag_id,
        series_title=args.series_title,
        season=season,
        keep_symlinks=args.keep_symlinks,
        skip_rescan=args.skip_rescan,
        skip_search=args.skip_search,
    )


if __name__ == "__main__":
    sys.exit(main())
