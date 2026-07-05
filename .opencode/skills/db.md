---
name: db
description: Patterns d'accès à la base de données SQLite
---

# db

## Schéma actuel

```sql
scans (id, path, status, broken_count, created_at, completed_at)
results (id, scan_id, symlink_path, target_path, status, action)
```

## Connexion

Toujours passer par `get_db` :

```python
from fastapi import Depends
from app.database import get_db
from aiosqlite import Connection

@router.get("/scans")
async def list_scans(db: Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM scans ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
```

## Règles

- Ne jamais ouvrir de connexion directe avec `aiosqlite.connect()` dans les routers ou services
- `aiosqlite.Row` est déjà configuré comme `row_factory` → compatible avec `dict(row)`
- Les mutations (`INSERT`, `UPDATE`, `DELETE`) doivent être suivies de `await db.commit()`
- Les chemins (`path`, `symlink_path`, `target_path`) sont stockés en TEXT
- Pour modifier le schéma : ajouter les instructions DDL dans `init_db()` avec `CREATE TABLE IF NOT EXISTS`
- Les migrations destructives (DROP, ALTER) sont à éviter ; privilégier l'ajout de colonnes
