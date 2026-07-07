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
| GET | `/results/{id}` | Détail d'un résultat |
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
| POST | `/api/results/{id}/ignore` | Ignorer un résultat |
| POST | `/api/results/{id}/fix` | Marquer manuellement comme corrigé |
| POST | `/api/results/{id}/recheck` | Remettre en file d'attente (`recherche`) |
| POST | `/api/results/{id}/verify-fs` | Vérifier le symlink sur le filesystem (→ `remplacé` si valide) |
| POST | `/api/results/{id}/process` | Traitement réel : DELETE API + recherche |
| GET | `/api/results/{id}/verifier` | Statut du cycle de vérification |
| POST | `/api/results/{id}/stop-verifier` | Arrêter le cycle de vérification (→ `non_remplacé` / `abandon`) |
| POST | `/api/results/batch` | Action groupée (process/fix/ignore/delete/recheck) |
| GET | `/api/results/ids` | IDs filtrés (pour selectAll batch) |
| GET | `/api/results/recent` | Résultats récents pour le dashboard |

## Configuration (JSON)

| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `/api/config` | Lire la configuration (clés API masquées) |
| POST | `/api/config` | Sauvegarder la configuration |
| GET | `/api/browse?path=...` | Explorateur de dossiers |
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

## Convention

- Les appels HTMX retournent des fragments HTML (partiels)
- Les appels API retournent du JSON
- Les actions destructives sont en POST et nécessitent confirmation explicite
- Les requêtes HTMX sont détectées via l'en-tête `HX-Request: true`
