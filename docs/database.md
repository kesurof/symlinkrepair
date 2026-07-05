# Base de données — Schéma SQLite

## Tables

### `scans`

```sql
CREATE TABLE scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT    NOT NULL,          -- 'radarr' | 'sonarr'
    mode        TEXT    NOT NULL DEFAULT 'simulate',  -- 'simulate' | 'clean'
    status      TEXT    NOT NULL DEFAULT 'running',   -- 'running' | 'completed' | 'error'
    total       INTEGER DEFAULT 0,
    broken      INTEGER DEFAULT 0,
    processed   INTEGER DEFAULT 0,
    summary     TEXT,                      -- JSON brut du script
    report_file TEXT,                      -- Chemin du fichier TSV
    created_at  TEXT    DEFAULT (datetime('now')),
    completed_at TEXT
);
```

### `results`

```sql
CREATE TABLE results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    source          TEXT    NOT NULL,      -- 'radarr' | 'sonarr'
    symlink_path    TEXT    NOT NULL,
    target_path     TEXT,
    media_type      TEXT,                  -- 'movie' | 'episode' | 'season'
    media_title     TEXT,                  -- Titre du film ou série
    season          INTEGER,
    episode         INTEGER,
    radarr_id       INTEGER,              -- MovieFile ID
    sonarr_id       INTEGER,              -- EpisodeFile ID
    tags            TEXT,                  -- JSON array
    status          TEXT    NOT NULL DEFAULT 'detected',
    action          TEXT,                  -- 'ignored' | 'fixed' | 'processed'
    action_date     TEXT,
    notes           TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id)
);
```

### `config`

```sql
CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL       -- JSON value
);
```

Ou stockage fichier JSON (`data/config.json`) — au choix selon la complexité.

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

## Index recommandés (V2)

```sql
CREATE INDEX idx_results_scan ON results(scan_id);
CREATE INDEX idx_results_status ON results(status);
CREATE INDEX idx_results_source ON results(source);
CREATE INDEX idx_scans_created ON scans(created_at);
```
