# API — Référence des endpoints

## Pages (HTML)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/` | Dashboard |
| GET | `/health` | Health check (status, database) |
| GET | `/scan` | Page de lancement de scan |
| GET | `/fastscan` | Page de scan rapide (éphémère, sans persistance) |
| GET | `/results` | Liste des éléments détectés |
| GET | `/results/{id}` | Détail d'un élément |
| GET | `/reports` | Historique des scans |
| GET | `/config` | Configuration + explorateur de dossiers |

## Actions scan

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/scan/{source}` | Déclencher un scan (radarr/sonarr) |
| GET | `/api/scan/{source}/status` | Statut d'un scan |
| POST | `/api/fast-scan` | Scan rapide éphémère (filesystem only) |

## Actions résultats (HTML / HTMX)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `/api/results/{id}/ignore` | Ignorer un élément |
| POST | `/api/results/{id}/recheck` | Revérifier un élément |
| POST | `/api/results/{id}/fix` | Marquer manuellement comme corrigé |
| POST | `/api/results/{id}/process` | Traitement réel : DELETE API + recherche |
| POST | `/api/results/batch` | Action groupée sur plusieurs IDs |

## Données de résultats (JSON)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/results/ids` | IDs des résultats filtrés (pour batch selectAll) |
| GET | `/api/stats` | Statistiques globales |
| POST | `/api/scans/delete` | Supprimer des scans et leurs résultats |

## Configuration (JSON)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/config` | Lire la configuration (clés API masquées) |
| POST | `/api/config` | Sauvegarder la configuration |
| GET | `/api/browse?path=...` | Explorateur de dossiers |
| POST | `/api/config/test-radarr` | Tester connexion Radarr |
| POST | `/api/config/test-sonarr` | Tester connexion Sonarr |

## Convention

- Les appels HTMX retournent des fragments HTML (partiels)
- Les appels API retournent du JSON
- Les actions destructives sont en POST et nécessitent une confirmation explicite
- Les requêtes HTMX sont détectées via l'en-tête `HX-Request: true`
