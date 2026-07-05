# Script Sonarr

**Fichier :** `docs/scripts/sonarr_cleanup_broken_alldebrid.py`

## Description

Script autonome de détection et nettoyage des symlinks cassés pointant vers
AllDebrid / Decypharr dans les bibliothèques Sonarr.

## Modes

- `--simulate` : analyse sans modification (par défaut)
- `--clean` : nettoyage réel avec suppression API Sonarr

## Paramètres supportés

| Paramètre | Type | Description |
|-----------|------|-------------|
| `--simulate` | flag | Mode simulation |
| `--clean` | flag | Mode nettoyage réel |
| `--limit` | int | Nombre max de fichiers à traiter |
| `--series-title` | str | Filtre par titre de série |
| `--season` | int | Filtre par numéro de saison |
| `--tags` | str | Filtre par tags (séparés par virgule) |
| `--keep-symlinks` | flag | Conserver les symlinks locaux |
| `--refresh` | flag | Refresh Sonarr après traitement |
| `--search` | flag | Recherche automatique après nettoyage |

## Particularité

Gestion du **mode saison entière** : si un épisode d'une saison est cassé,
toute la saison peut être traitée en un bloc. Le script ne coupe jamais une
saison en deux lorsque `--limit` est appliqué.

## Configuration

Fichier : à côté du script, nommé `sonarr_cleanup.json`

```json
{
  "SONARR_URL": "http://sonarr:8989",
  "SONARR_API_KEY": "",
  "SONARR_CONTAINER": "sonarr",
  "SONARR_LIBRARY_ROOTS": ["/mnt/medias/Series"],
  "SONARR_TARGET_PREFIXES": ["/mnt/decypharrsonarr/alldebrid/"],
  "DISCORD_WEBHOOK_URL": "",
  "DISCORD_NOTIFICATIONS_ENABLED": false
}
```

## Sortie JSON (stdout)

```json
{
  "status": "completed",
  "mode": "simulate",
  "total_symlinks": 320,
  "monitored_symlinks": 45,
  "broken_symlinks": 12,
  "affected_series": ["Breaking Bad"],
  "affected_seasons": {"Breaking Bad": [5]},
  "processed": 12,
  "deleted_api": 0,
  "refresh_requested": false,
  "search_requested": false,
  "season_search_requested": 2,
  "deleted_symlinks": 0,
  "errors": [],
  "report_file": "/tmp/sonarr_cleanup_2025-07-05.tsv"
}
```

## Intégration

L'application appelle ce script en sous-processus via `app/services/sonarr.py`.
Les résultats sont parsés, stockés en base, et rendus dans l'interface.
