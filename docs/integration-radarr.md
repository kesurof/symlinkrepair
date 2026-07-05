# Intégration Radarr

## API REST

| Méthode | Endpoint | Usage | Paramètres |
|---------|----------|-------|------------|
| `GET` | `/api/v3/system/status` | Test connexion, version | — |
| `GET` | `/api/v3/tag` | Liste des tags pour filtrage | — |
| `DELETE` | `/api/v3/moviefile/{id}` | Supprimer un MovieFile | `deleteFile=false` |
| `POST` | `/api/v3/command` | Refresh / Search | `{"name": "RefreshMovie", "movieIds": [...]}` |
| `POST` | `/api/v3/command` | Recherche automatique | `{"name": "MoviesSearch", "movieIds": [...]}` |
| `GET` | `/api/v3/queue` | État de la file d'attente | — |

## Correspondance symlink → MovieFile

**Méthode retenue : interrogation directe de la base SQLite Radarr**

Le script existant utilise `docker cp` pour récupérer `/config/radarr.db` depuis
le conteneur Radarr, puis exécute une requête SQL qui joint `MovieFiles`,
`Movies` et `MovieMetadata` pour construire le chemin complet de chaque fichier :

```sql
SELECT
    mf.Id AS movie_file_id,
    mf.MovieId AS movie_id,
    mf.RelativePath AS relative_path,
    m.Path AS movie_path,
    m.Tags AS movie_tags,
    mm.Title AS movie_title,
    mm.Year AS movie_year
FROM MovieFiles mf
JOIN Movies m ON m.Id = mf.MovieId
LEFT JOIN MovieMetadata mm ON mm.Id = m.MovieMetadataId
```

Le matching se fait par **chemin absolu** : `movie_path + '/' + relative_path` =
chemin du symlink sur le système de fichiers.

**Alternative API REST possible :**

```http
GET /api/v3/moviefile?movieId={movieId}
```

Mais la méthode SQLite est plus performante pour scanner des milliers de fichiers
en une seule requête plutôt que N appels API.

## Flux applicatif

```
SymlinkRepair                          Radarr
     │                                   │
     │── GET /api/v3/system/status ─────→│  Test connexion
     │←──────────────────────────────────│
     │                                   │
     │── docker cp radarr:/config/radarr.db ─→│  Copie DB
     │←──────────────────────────────────│
     │                                   │
     │── requête SQL (MovieFiles + Movies + MovieMetadata)
     │                                   │
     │── scan filesystem (LIBRARY_ROOTS) │
     │── matching path → movie_file_id   │
     │                                   │
     │── DELETE /api/v3/moviefile/{id} ──→│  Nettoyage
     │←──────────────────────────────────│
     │                                   │
     │── POST /api/v3/command (Refresh) ─→│
     │── POST /api/v3/command (Search) ───→│
     │←──────────────────────────────────│
```

## Implémentation dans l'application

Le service `app/services/radarr.py` expose :

- `test_connection(url, api_key)` → `bool`
- `fetch_tags(url, api_key)` → `list[dict]`
- `fetch_database(container)` → `str` (copie locale de radarr.db)
- `load_movie_records(db_path)` → `list[MovieFile]`
- `delete_movie_file(url, api_key, file_id)` → `bool`
- `refresh_movie(url, api_key, movie_ids)` → `bool`
- `search_movies(url, api_key, movie_ids)` → `bool`
- `fetch_queue(url, api_key)` → `int` (totalRecords)
