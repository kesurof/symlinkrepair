# Base de données — Schéma SQLite

Fichier : `data/symlinkrepair.db` (ignoré par git, créé automatiquement au démarrage).

## Tables

### `scans`

```sql
CREATE TABLE scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,             -- 'radarr' | 'sonarr'
    mode            TEXT    NOT NULL DEFAULT 'simulate', -- 'simulate' | 'clean'
    status          TEXT    NOT NULL DEFAULT 'running',  -- 'running' | 'completed' | 'error'
    total           INTEGER DEFAULT 0,            -- Symlinks totaux scannés
    broken          INTEGER DEFAULT 0,            -- Symlinks cassés trouvés
    processed       INTEGER DEFAULT 0,            -- Nombre de fichiers traités (nettoyage clean)
    summary         TEXT,                          -- Résumé texte
    report_file     TEXT,                          -- Chemin du fichier rapport (optionnel)
    created_at      TEXT    DEFAULT (datetime('now')),
    completed_at    TEXT
);
```

### `results`

```sql
CREATE TABLE results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    source          TEXT    NOT NULL,              -- 'radarr' | 'sonarr'
    symlink_path    TEXT    NOT NULL,              -- Chemin absolu du symlink
    target_path     TEXT,                          -- Cible du symlink (lue par readlink)
    media_type      TEXT,                          -- 'movie' | 'episode' | NULL
    media_title     TEXT,                          -- Titre du film ou série
    season          INTEGER,                       -- Sonarr uniquement
    episode         INTEGER,                       -- Sonarr uniquement
    file_id         INTEGER,                       -- movie_file_id | episode_file_id
    movie_id        INTEGER,                       -- Radarr uniquement
    series_id       INTEGER,                       -- Sonarr uniquement
    tags            TEXT,                          -- JSON array des tags Radarr/Sonarr
    detection       TEXT    NOT NULL DEFAULT 'broken_symlink',
    status          TEXT    NOT NULL DEFAULT 'détecté',
    action          TEXT,                          -- 'ignored' | 'manual_fix' | 'api_delete' | 'verifier_ok' | 'verifier_fail' | 'abandon'
    search_count    INTEGER DEFAULT 0,             -- Nombre de traitements effectués
    action_date     TEXT,
    notes           TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id)
);
```

### Index

```sql
CREATE INDEX idx_results_scan ON results(scan_id);
CREATE INDEX idx_results_status ON results(status);
CREATE INDEX idx_scans_created ON scans(created_at);
```

## Statuts possibles (results)

| Statut | Description |
|--------|-------------|
| `détecté` | Détecté par un scan, en attente d'action |
| `recherche` | En cours de revérification (action "Revérifier") |
| `en_attente` | DELETE API envoyé, vérification en cours |
| `remplacé` | Symlink remplacé ou marqué manuellement comme corrigé |
| `non_remplacé` | Vérifié : le symlink n'a pas été remplacé (ou cycle abandonné) |
| `ignoré` | Ignoré par l'utilisateur |
| `échoué` | L'action API a échoué |

## Actions possibles (results.action)

| Action | Déclencheur |
|--------|-------------|
| `ignored` | Action "Ignorer" |
| `manual_fix` | Action "Marquer remplacé" |
| `api_delete` | Action "Traiter" (DELETE API Radarr/Sonarr) |
| `verifier_ok` | Vérificateur : symlink remplacé |
| `verifier_fail` | Vérificateur : symlink non remplacé |
| `abandon` | Cycle de vérification arrêté manuellement |
| `auto_fix` | Traitement : symlink déjà valide |
| `verify_fs` | Vérification filesystem manuelle |
| `recheck` | Action "Revérifier" |
| `cleaned_duplicate` | Migration : doublon nettoyé |
| `*_sibling` | Synchronisation d'un doublon frère |

## Accès

Toujours via `app.database.get_db()` :

```python
from fastapi import Depends
from aiosqlite import Connection
from app.database import get_db

@router.get("/results")
async def list_results(db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results ORDER BY id DESC")
    return [dict(row) for row in await cursor.fetchall()]
```
