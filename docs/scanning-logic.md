# Logique de scan

## Algorithme général

```
1. Préparer
   ├── Charger config (data/config.json)
   ├── Tester connexion Radarr/Sonarr (optionnel)
   └── Copier les bases SQLite depuis les conteneurs (docker cp)

2. Scanner le filesystem
   ├── Pour chaque LIBRARY_ROOT
   │   ├── Parcourir récursivement (depth-first, stack)
   │   ├── Pour chaque entrée :
   │   │   ├── Si c'est un dossier → empiler
   │   │   ├── Si c'est un symlink → inspecter
   │   │   └── Ignorer les fichiers normaux
   │   └── Compter total_symlinks
   └── Collecter les symlinks cassés + prefix match

3. Croiser avec Radarr/Sonarr
   ├── Charger les MovieFiles / EpisodeFiles depuis la DB SQLite
   ├── Indexer par chemin absolu
   └── Pour chaque symlink cassé :
       ├── Chercher le chemin dans l'index
       ├── Si trouvé → créer un target avec movie/series info
       └── Si non trouvé → ignorer (symlink orphelin)

4. Filtrer
   ├── Appliquer filtre titre (substring case-insensitive)
   ├── Appliquer filtre tags (intersection set)
   ├── Appliquer filtre saison (Sonarr)
   └── Appliquer limite (truncate)

5. Action
   ├── Simulation : afficher les targets, ne rien modifier
   └── Nettoyage réel :
       ├── DELETE /api/v3/moviefile/{id}?deleteFile=false
       │   ou DELETE /api/v3/episodefile/{id}
       ├── Supprimer le symlink local (optionnel)
       ├── POST RefreshMovie / RescanSeries
       └── POST MoviesSearch / SeasonSearch (optionnel)
```

## Structure de données

### Entrée (filesystem)

```python
class SymlinkInfo(TypedDict):
    path: str                    # Chemin absolu du symlink
    target: str                  # Cible brute (lue par readlink)
    target_resolved: str         # Cible résolue en absolu
    exists: bool                 # La cible existe-t-elle ?
    broken: bool                 # Cible manquante ?
    matches_prefix: bool         # Cible commence par un TARGET_PREFIX ?
```

### Correspondance Radarr

```python
class MovieFile(TypedDict):
    movie_file_id: int
    movie_id: int
    relative_path: str
    movie_path: str              # Racine du film dans Radarr
    full_path: str               # movie_path + '/' + relative_path
    movie_title: str
    movie_year: int
    tags: list[int]
```

### Target (résultat du matching)

```python
class ScanTarget(TypedDict):
    source: str                  # 'radarr' | 'sonarr'
    symlink_path: str
    symlink_target: str
    media_type: str              # 'movie' | 'episode'
    media_title: str
    season: int | None           # Sonarr only
    episode: int | None          # Sonarr only
    file_id: int                 # movie_file_id ou episode_file_id
    movie_id: int | None         # Radarr only
    series_id: int | None        # Sonarr only
    tags: list[int]
    reason: str                  # 'broken_symlink'
```

### Résultat de scan

```python
class ScanResult(TypedDict):
    status: str                  # 'completed' | 'error'
    mode: str                    # 'simulate' | 'clean'
    symlinks_total: int
    symlinks_matching_prefix: int
    broken_symlinks: int
    targets_before_limit: int
    targets_selected: int
    affected_movies: int         # Radarr
    affected_series: list        # Sonarr
    affected_seasons: dict       # Sonarr
    processed: int
    errors: list[str]
    report_path: str | None
```

## Détection des symlinks cassés

```python
import os
from pathlib import Path

def iter_symlinks(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            for entry in os.scandir(current):
                if entry.is_symlink():
                    yield entry.path
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
        except OSError:
            continue  # permission, etc.

def inspect_symlink(path: str, prefixes: list[str]) -> SymlinkInfo:
    target = os.readlink(path)
    target_resolved = target
    if not os.path.isabs(target):
        target_resolved = os.path.join(os.path.dirname(path), target)
    target_resolved = os.path.normpath(target_resolved)

    exists = os.path.exists(target_resolved)
    matches = any(target_resolved.startswith(p) for p in prefixes)

    return {
        "path": path,
        "target": target,
        "target_resolved": target_resolved,
        "exists": exists,
        "broken": not exists,
        "matches_prefix": matches,
    }
```

## Cycle de vie d'un scan

```
[UI]                    [API]                   [Service]
  │                        │                        │
  │── POST /scan/radarr ──→│                        │
  │                        │── INSERT scans ────────→│  (status=running)
  │                        │── start_scan_async ────→│
  │                        │←── scan_id ────────────│
  │←── scan_id ───────────│                        │
  │                        │                        │
  │── GET /scan/{id}/status ──→│                    │  (polling 2s)
  │                        │── SELECT status ──────→│
  │←── {status, progress}─│                        │
  │                        │                        │
  │ (scan terminé)         │── UPDATE scans ───────→│  (status=completed)
  │                        │── INSERT results ─────→│
  │                        │                        │
  │── GET /results?scan_id=42 ──→│                  │
  │←── liste résultats ───│                        │
```

## Verrouillage

Un seul scan par source à la fois :

```
app/
└── services/
    └── scanner.py
        ├── _radarr_lock: asyncio.Lock()
        ├── _sonarr_lock: asyncio.Lock()
        ├── is_running(source) → bool
        ├── start_scan(source, params) → scan_id
        └── get_status(scan_id) → dict
```

- Si `_radarr_lock` est acquis, un deuxième scan Radarr est refusé
- Les scans Radarr et Sonarr peuvent tourner en parallèle
- Le lock est relâché automatiquement à la fin du scan (même en cas d'erreur)
