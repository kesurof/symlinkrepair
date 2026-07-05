# Intégration Sonarr

## API REST

| Méthode | Endpoint | Usage | Paramètres |
|---------|----------|-------|------------|
| `GET` | `/api/v3/system/status` | Test connexion, version | — |
| `GET` | `/api/v3/tag` | Liste des tags pour filtrage | — |
| `DELETE` | `/api/v3/episodefile/{id}` | Supprimer un EpisodeFile | — |
| `POST` | `/api/v3/command` | Rescan série | `{"name": "RescanSeries", "seriesId": id}` |
| `POST` | `/api/v3/command` | Recherche saison | `{"name": "SeasonSearch", "seriesId": id, "seasonNumber": n}` |
| `GET` | `/api/v3/queue` | État de la file d'attente | — |

## Correspondance symlink → EpisodeFile

**Méthode retenue : interrogation directe de la base SQLite Sonarr**

Même approche que Radarr : copie de la base depuis le conteneur et requête SQL
joignant `EpisodeFiles`, `Episodes`, `Series` et `SeriesMetadata` :

```sql
SELECT
    ef.Id AS episode_file_id,
    ef.SeriesId AS series_id,
    ef.RelativePath AS relative_path,
    e.SeasonNumber AS season,
    e.EpisodeNumber AS episode,
    s.Path AS series_path,
    s.Tags AS series_tags,
    sm.Title AS series_title
FROM EpisodeFiles ef
JOIN Episodes e ON e.EpisodeFileId = ef.Id
JOIN Series s ON s.Id = ef.SeriesId
LEFT JOIN SeriesMetadata sm ON sm.Id = s.SeriesMetadataId
```

Le matching se fait par **chemin absolu** : `series_path + '/' + relative_path`.

## Particularité Sonarr

Sonarr gère le **mode saison entière** : si un épisode d'une saison est cassé,
toute la saison peut être traitée en un bloc. Le script ne coupe jamais une
saison en deux lorsque `--limit` est appliqué.

## Implémentation dans l'application

Le service `app/services/sonarr.py` expose :

- `test_connection(url, api_key)` → `bool`
- `fetch_tags(url, api_key)` → `list[dict]`
- `fetch_database(container)` → `str` (copie locale de sonarr.db)
- `load_episode_records(db_path)` → `list[EpisodeFile]`
- `delete_episode_file(url, api_key, file_id)` → `bool`
- `rescan_series(url, api_key, series_id)` → `bool`
- `search_season(url, api_key, series_id, season)` → `bool`
- `fetch_queue(url, api_key)` → `int` (totalRecords)
