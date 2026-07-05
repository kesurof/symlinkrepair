# API — Référence des endpoints

## Pages (HTML)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/` | Dashboard |
| GET | `/scan` | Page de scan |
| GET | `/results` | Liste des éléments détectés |
| GET | `/results/{id}` | Détail d'un élément |
| GET | `/reports` | Rapports d'exécution |
| GET | `/config` | Configuration et explorateur de dossiers |

## Actions (HTMX — fragments HTML)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/scan/radarr` | Lancer scan Radarr (simulation) |
| GET | `/scan/sonarr` | Lancer scan Sonarr (simulation) |
| GET | `/scan/radarr?mode=clean` | Lancer scan Radarr (nettoyage réel) |
| GET | `/scan/sonarr?mode=clean` | Lancer scan Sonarr (nettoyage réel) |
| GET | `/results/{id}/detail` | Fragment détail |
| POST | `/results/{id}/ignore` | Ignorer un élément |
| POST | `/results/{id}/fixed` | Marquer comme corrigé |
| POST | `/results/{id}/recheck` | Revérifier un élément |

## Data (JSON)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stats` | Statistiques globales |
| GET | `/api/config` | Lire la configuration (clés API masquées) |
| POST | `/api/config` | Sauvegarder la configuration |
| GET | `/api/browse?path=...` | Explorateur de dossiers |
| POST | `/api/config/test-radarr` | Tester connexion Radarr |
| POST | `/api/config/test-sonarr` | Tester connexion Sonarr |

## Convention

- Les appels HTMX retournent des fragments HTML (partiels)
- Les appels API retournent du JSON
- Les actions destructives sont en POST et nécessitent un paramètre `confirm=true`
