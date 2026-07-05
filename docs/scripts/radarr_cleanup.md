# Script Radarr

**Fichier :** `docs/scripts/radarr_cleanup_broken_alldebrid.py`

## Description

Script autonome de détection et nettoyage des symlinks cassés pointant vers
AllDebrid / Decypharr dans les bibliothèques Radarr.

## Modes

- `--simulate` : analyse sans modification (par défaut)
- `--clean` : nettoyage réel avec suppression API Radarr

## Paramètres supportés

| Paramètre | Type | Description |
|-----------|------|-------------|
| `--simulate` | flag | Mode simulation |
| `--clean` | flag | Mode nettoyage réel |
| `--limit` | int | Nombre max de fichiers à traiter |
| `--movie-title` | str | Filtre par titre de film |
| `--tags` | str | Filtre par tags (séparés par virgule) |
| `--keep-symlinks` | flag | Conserver les symlinks locaux |
| `--refresh` | flag | Refresh Radarr après traitement |
| `--search` | flag | Recherche automatique après nettoyage |

## Configuration

Fichier : à côté du script, nommé `radarr_cleanup.json`

```json
{
  "RADARR_URL": "http://radarr:7878",
  "RADARR_API_KEY": "",
  "RADARR_CONTAINER": "radarr",
  "RADARR_LIBRARY_ROOTS": ["/mnt/medias/Films"],
  "RADARR_TARGET_PREFIXES": ["/mnt/decypharr/alldebrid/"],
  "DISCORD_WEBHOOK_URL": "",
  "DISCORD_NOTIFICATIONS_ENABLED": false
}
```

## Sortie JSON (stdout)

```json
{
  "status": "completed",
  "mode": "simulate",
  "total_symlinks": 150,
  "monitored_symlinks": 23,
  "broken_symlinks": 5,
  "affected_movies": ["Batman Begins"],
  "processed": 5,
  "deleted_api": 0,
  "refresh_requested": false,
  "search_requested": false,
  "deleted_symlinks": 0,
  "errors": [],
  "report_file": "/tmp/radarr_cleanup_2025-07-05.tsv"
}
```

## Intégration

L'application appelle ce script en sous-processus via `app/services/radarr.py`.
Les résultats sont parsés, stockés en base, et rendus dans l'interface.
