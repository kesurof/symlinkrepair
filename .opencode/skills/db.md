---
name: db
description: Patterns d'accès à la base de données SQLite
---

# db

## Schéma

### `scans`

```sql
CREATE TABLE scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,             -- 'radarr' | 'sonarr'
    mode            TEXT NOT NULL DEFAULT 'simulate',
    status          TEXT NOT NULL DEFAULT 'running',
    total           INTEGER DEFAULT 0,
    broken          INTEGER DEFAULT 0,
    processed       INTEGER DEFAULT 0,
    summary         TEXT,
    report_file     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);
```

### `results`

```sql
CREATE TABLE results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL,
    source          TEXT NOT NULL,
    symlink_path    TEXT NOT NULL,
    target_path     TEXT,
    media_type      TEXT,
    media_title     TEXT,
    season          INTEGER,
    episode         INTEGER,
    file_id         INTEGER,
    movie_id        INTEGER,
    series_id       INTEGER,
    tags            TEXT,
    detection       TEXT NOT NULL DEFAULT 'broken_symlink',
    status          TEXT NOT NULL DEFAULT 'détecté',
    action          TEXT,
    search_count    INTEGER DEFAULT 0,
    action_date     TEXT,
    notes           TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id)
);
```

## Connexion

Toujours passer par `get_db` :

```python
from fastapi import Depends
from app.database import get_db
from aiosqlite import Connection

@router.get("/results")
async def list_results(db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM results ORDER BY id DESC")
    return [dict(row) for row in await cursor.fetchall()]
```

## Règles

- Ne jamais ouvrir de connexion directe avec `aiosqlite.connect()` dans les routers
- `aiosqlite.Row` est déjà configuré comme `row_factory` → compatible avec `dict(row)`
- Les mutations (`INSERT`, `UPDATE`, `DELETE`) doivent être suivies de `await db.commit()`
- Les chemins (`path`, `symlink_path`, `target_path`) sont stockés en TEXT
- Les `LIKE` queries utilisent `?` param binding (pas de f-string pour les valeurs)
- Les `IN (...)` queries utilisent `','.join('?' for _ in ids)` + passage des ids comme params

## Statuts (results.status)

| Valeur | Signification |
|--------|--------------|
| `détecté` | Détecté par un scan, en attente d'action |
| `surveillance` | DELETE API envoyé, vérification en cours |
| `remplacé` | Symlink remplacé ou marqué manuellement comme corrigé |
| `non_remplacé` | Vérifié : symlink non remplacé (ou cycle abandonné) |
| `ignoré` | Ignoré par l'utilisateur |
| `échoué` | L'action API a échoué |

## Actions batch

| action | Déclencheur | Statut |
|--------|-------------|--------|
| action | Déclencheur | Statut |
|--------|-------------|--------|
| `process` | Traiter (DELETE API) | `surveillance` |
| `process_season` | Traiter saison Sonarr (DELETE API + search) | `surveillance` / `échoué` |
| `verify_season` | Vérifier saison Sonarr (filesystem check) | `remplacé` / unchanged |
| `fix` | Marquer remplacé | `remplacé` |
| `ignore` | Ignorer | `ignoré` |
| `delete` | Supprimer | — (DELETE row) |

## Déduplication

La page `/results` utilise `GROUP BY symlink_path, source` pour afficher uniquement le dernier résultat (MAX id) par paire (path, source). Le toggle "Masquer les doublons" dans l'UI permet de voir tous les résultats.
