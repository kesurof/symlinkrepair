# API — Référence des endpoints

## Pages (HTML)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/` | Dashboard |
| GET | `/health` | Health check (status, database) |
| GET | `/config` | Configuration + explorateur de dossiers |
| GET | `/scan` | Page de scan (complet + rapide fusionnés) |
| GET | `/fastscan` | Redirect 301 vers `/scan?mode=fast` |
| GET | `/results` | Liste des résultats (avec pagination, filtres) |
| GET | `/results/{result_id}` | Détail d'un résultat |
| GET | `/reports` | Historique des scans |

## Actions scan

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/scan/{source}` | Déclencher un scan (radarr/sonarr) |
| GET | `/api/scan/{source}/status` | Statut d'un scan |
| POST | `/api/fast-scan` | Scan rapide éphémère |

## Actions résultats

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/results/{result_id}/ignore` | Ignorer un résultat |
| POST | `/api/results/{result_id}/fix` | Marquer manuellement comme corrigé |
| POST | `/api/results/{result_id}/recheck` | Remettre en file d'attente (`recherche`) |
| POST | `/api/results/{result_id}/verify-fs` | Vérifier le symlink sur le filesystem (→ `remplacé` si valide) |
| POST | `/api/results/{result_id}/process` | Traitement réel : DELETE API + recherche |
| GET | `/api/results/{result_id}/verifier` | Statut du cycle de vérification |
| POST | `/api/results/{result_id}/stop-verifier` | Arrêter le cycle de vérification (→ `non_remplacé` / `abandon`) |
| POST | `/api/results/batch` | Action groupée (process/fix/ignore/delete/recheck/process_season/verify_season) |
| GET | `/api/results/ids` | IDs filtrés (pour selectAll batch) |
| GET | `/api/results/recent` | Résultats récents pour le dashboard |

## Configuration (JSON)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/config` | Lire la configuration (clés API masquées) |
| POST | `/api/config` | Sauvegarder la configuration |
| GET | `/api/browse?path=...` | Explorateur de dossiers |
| GET | `/api/config/default-browse-roots` | Racines de navigation par défaut |
| POST | `/api/browse/validate` | Valider un chemin d'accès |
| POST | `/api/config/test-radarr` | Tester connexion Radarr |
| POST | `/api/config/test-sonarr` | Tester connexion Sonarr |

## Version

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/version` | Version de l'application |

## Statistiques

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/stats` | Statistiques globales |
| GET | `/api/stats/history` | Historique des stats (30/90 jours) |
| GET | `/api/scans/ids` | IDs filtrés des scans (pour selectAll batch) |
| POST | `/api/scans/delete` | Supprimer des scans et leurs résultats |

### Réponse de `POST /api/results/batch` pour `process_season`

```json
{
  "ok": true,
  "error": "",
  "affected": 0,
  "total": 5,
  "search_triggered": true
}
```

- `ok` : true si au moins un épisode a été supprimé OU si la recherche Sonarr a été déclenchée
- `error` : message d'erreur si tout a échoué sans recherche
- `affected` : nombre d'épisodes supprimés via l'API Sonarr (peut être 0 si les `file_id` étaient absents)
- `total` : nombre total de résultats trouvés dans la base pour cette saison
- `search_triggered` : true si une commande `RescanSeries` ou `SeasonSearch` a été soumise à Sonarr

### Réponse de `POST /api/results/batch` pour `verify_season`

```json
{
  "ok": true,
  "verified": 3,
  "total": 5
}
```

- `verified` : nombre de symlinks valides trouvés sur le filesystem (marqués `remplacé`)
- `total` : nombre total de résultats vérifiés pour la saison

## Convention

- Les appels HTMX retournent des fragments HTML (partiels)
- Les appels API retournent du JSON
- Les actions destructives sont en POST et nécessitent confirmation explicite
- Les requêtes HTMX sont détectées via l'en-tête `HX-Request: true`
