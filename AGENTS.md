# Instructions pour les agents opencode

## Stack
- **Backend** : FastAPI (Python ≥3.11)
- **Version** : via `app/version.py` (git describe / VERSION file)
- **Templates** : Jinja2
- **Frontend** : HTMX 2.x + Alpine.js 3.x + Tailwind CSS (CDN) + Inter (Google Fonts)
- **Icônes** : Heroicons SVG inline
- **Design** : Mobile-first, dark mode, palette brand indigo
- **Base de données** : SQLite via aiosqlite
- **Déploiement** : Docker (python:3.12-slim)

## Conventions
- Pas de commentaires dans le code sauf si nécessaire
- Pas de chaîne de build frontend (pas de npm, Vite, Webpack)
- Les dépendances sont dans `pyproject.toml` uniquement
- Les routes sont dans `app/routers/`
- La logique métier dans `app/services/`
- Les modèles Pydantic dans `app/models/`
- Les templates Jinja2 dans `app/templates/`
- Les fichiers statiques dans `app/static/`
- L'instance Jinja2Templates partagée dans `app/templates.py`
- **Layout** : sidebar desktop (rétractable) + bottom nav mobile (5 onglets)
- **Animations** CSS dans `app/static/app.css` (fade-in, slide-up, skeleton)

## HTMX + Alpine — Règles
- **NE PAS** stocker l'état serveur dans Alpine (`x-text`, `x-init`)
- **NE PAS** utiliser d'événements custom ou `htmx:afterSwap` pour synchroniser
- **TOUJOURS** utiliser `hx-swap-oob="true"` pour mettre à jour les éléments du parent
- Les données de pagination dans un div caché avec `data-*` attributes
- Alpine réservé à l'interactivité locale (sélection, batch, modales)
- Détection HTMX : `request.headers.get("hx-request") == "true"`

## Commandes
```bash
# Lancer en dev
make dev

# Lint
make lint

# Formater le code
make format

# Lancer les tests
make test

# Lancer avec Docker
make docker

# Pusher le code
make deploy
```

## Tests
- Framework : pytest
- Fichiers dans `tests/`
- Lancer avec `make test` ou `python -m pytest -v`

## Pre-commit
- Config dans `.pre-commit-config.yaml`
- Ruff check + format automatique avant chaque commit
- Installer avec `pre-commit install`

## Endpoints

### Pages (HTML)
- `GET /` — Dashboard avec stats
- `GET /health` — Health check (status, database)
- `GET /config` — Configuration + explorateur de dossiers
- `GET /scan` — Page de scan (complet + rapide fusionnés)
- `GET /results` — Liste des résultats (avec pagination, filtres)
- `GET /results/{id}` — Détail d'un résultat
- `GET /reports` — Historique des scans
- `GET /fastscan` → redirect 301 vers `/scan?mode=fast`

### Actions scan
- `POST /api/scan/{source}` — Déclencher un scan (radarr/sonarr)
- `GET /api/scan/{source}/status` — Statut d'un scan
- `POST /api/fast-scan` — Scan rapide éphémère

### Actions résultats
- `POST /api/results/{id}/ignore` — Ignorer un résultat
- `POST /api/results/{id}/fix` — Marquer manuellement comme corrigé
- `POST /api/results/{id}/recheck` — Remettre en file d'attente (`recherche`)
- `POST /api/results/{id}/verify-fs` — Vérifier le symlink sur le filesystem (→ `remplacé` si valide)
- `POST /api/results/{id}/process` — Traitement réel : DELETE API + recherche
- `GET /api/results/{id}/verifier` — Statut du cycle de vérification
- `POST /api/results/{id}/stop-verifier` — Arrêter le cycle de vérification (→ `non_remplacé` / `abandon`)
- `POST /api/results/{id}/verify-fs` — Vérifier le symlink sur le filesystem (→ `remplacé` si valide)
- `POST /api/results/batch` — Action groupée (process/fix/ignore/delete/recheck/process_season/verify_season)
- `GET /api/results/ids` — IDs filtrés (pour selectAll batch)
- `GET /api/results/recent` — Résultats récents pour le dashboard

### Configuration
- `GET /api/config` — Lire la config (secrets masqués)
- `POST /api/config` — Sauvegarder la config
- `GET /api/browse?path=...` — Explorateur de dossiers
- `POST /api/config/test-radarr` — Tester connexion Radarr
- `POST /api/config/test-sonarr` — Tester connexion Sonarr

### Version
- `GET /api/version` — Version de l'application

### Statistiques
- `GET /api/stats` — Statistiques globales
- `GET /api/scans/ids` — IDs filtrés des scans (pour selectAll batch)
- `POST /api/scans/delete` — Supprimer des scans et leurs résultats

## Base de données
- Fichier SQLite dans `data/symlinkrepair.db` (ignoré par git)
- Initialisation automatique au démarrage via `app/database.py`
- Tables : `scans`, `results` (avec index sur scan_id, status, created_at)

## Actions batch disponibles
- **Traiter** (`process`) — DELETE API Radarr/Sonarr + recherche auto (supporte `delete_season` pour Sonarr)
- **Traiter une saison** (`process_season`) — DELETE API Sonarr des épisodes encore référencés + marquage `recherche` pour ceux sans `file_id` + recherche Sonarr systématique de toute la saison (nécessite `series_id` + `season` dans le body). Retourne `search_triggered: true` si la recherche a été déclenchée.
- **Vérifier une saison** (`verify_season`) — Vérifie sur le filesystem tous les épisodes d'une saison, marque `remplacé` ceux qui sont valides (nécessite `series_id` + `season` dans le body)
- **Marquer remplacé** (`fix`) — Flag manuel (symlink marqué comme remplacé)
- **Ignorer** (`ignore`) — Cache le résultat
- **Revérifier** (`recheck`) — Remet en file d'attente (`recherche`)
- **Supprimer** (`delete`) — Supprime la ligne en base

## Statuts des résultats
`détecté` / `recherche` → `en_attente` → `remplacé` / `non_remplacé` / `ignoré` / `échoué`

## Actions des résultats (results.action)
| Action | Déclencheur |
|--------|-------------|
| `ignored` | Action "Ignorer" |
| `manual_fix` | Action "Marquer remplacé" |
| `api_delete` | Action "Traiter" (DELETE API) |
| `verifier_ok` | Vérificateur : symlink remplacé |
| `verifier_fail` | Vérificateur : symlink non remplacé |
| `abandon` | Cycle de vérification arrêté manuellement |
| `auto_fix` | Traitement : symlink déjà valide |
| `verify_fs` | Vérification filesystem manuelle |
| `recheck` | Action "Revérifier" |
| `cleaned_duplicate` | Migration : doublon nettoyé |
| `api_error` | Échec de l'API Radarr/Sonarr |
| `*_sibling` | Synchronisation d'un doublon frère |

## Sécurité
- Aucun secret dans le code
- Configuration via variables d'environnement
- Clés API masquées dans l'interface
- Explorateur de dossiers restreint aux `browse_roots`
- Actions destructives avec confirmation HTMX / Alpine

## État du projet
- [x] Module Config (CRUD, browse, test connexion)
- [x] Module Scan (filesystem, bases Radarr/Sonarr, orchestrateur async)
- [x] Module Résultats (liste, détail, actions statut, batch)
- [x] Dashboard et statistiques de base
- [x] Actions de nettoyage réelles (DELETE API)
- [x] Filtres avancés + pagination sur page résultats
- [x] Déduplication (GROUP BY symlink_path + source)
- [x] Page de scan améliorée (options, confirmation 2 étapes)
- [x] Scan rapide éphémère (fusionné dans /scan)
- [x] Docker compose vérifié
- [x] Notifications Discord (webhook configurable, envoi scan + nettoyage)
- [x] Scans automatiques planifiés (intervalle configurable dans /config)
- [x] Vérificateur asynchrone (surveille remplacement des symlinks)
- [x] Sélection multiple et actions batch (process, fix, ignore, delete, process_season)
- [x] **Groupement par saison** : Sonarr groupé par (series_id, season) avec accordéon, barre de progression, bouton "Traiter la saison", vérification individuelle conservée
- [x] **Refonte UI** : sidebar desktop + bottom nav mobile, dark mode, mobile-first, Heroicons
- [x] **Gestion de version** : `/api/version`, affichage sidebar, `VERSION` file en Docker
- [x] **Déduplication** doublons : migration nettoyage + `_sync_siblings` + stats dédupliquées
- [x] **Auto-fix** : si symlink déjà valide → marque `remplacé` sans erreur
- [x] **CI manuelle** : `workflow_dispatch` GitHub Actions, plus de build automatique sur push
