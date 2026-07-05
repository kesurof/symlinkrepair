# Instructions pour les agents opencode

## Stack
- **Backend** : FastAPI (Python ≥3.11)
- **Templates** : Jinja2
- **Frontend** : HTMX 2.x + Alpine.js 3.x + Tailwind CSS (CDN)
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
- Le fichier statique éventuel dans `app/static/`
- L'instance Jinja2Templates partagée dans `app/templates.py`

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
- `GET /health` — health check (status, database)
- `GET /` — Dashboard avec stats
- `GET /config` — Configuration + explorateur de dossiers
- `GET /scan` — Page de lancement de scan
- `GET /results` — Liste des résultats
- `GET /results/{id}` — Détail d'un résultat
- `GET /reports` — Historique des scans
- `POST /api/scan/{source}` — Déclencher un scan (radarr/sonarr)
- `GET /api/scan/{source}/status` — Statut d'un scan
- `GET /api/config` — Lire la config (secrets masqués)
- `POST /api/config` — Sauvegarder la config
- `GET /api/browse?path=...` — Explorateur de dossiers
- `POST /api/config/test-radarr` — Tester connexion Radarr
- `POST /api/config/test-sonarr` — Tester connexion Sonarr
- `GET /api/stats` — Statistiques globales
- `POST /api/results/{id}/ignore` — Ignorer un résultat
- `POST /api/results/{id}/recheck` — Revérifier un résultat

## Base de données
- Fichier SQLite dans `data/symlinkrepair.db` (ignoré par git)
- Initialisation automatique au démarrage via `app/database.py`
- Tables : `scans`, `results` (avec index)

## Sécurité
- Aucun secret dans le code
- Configuration via variables d'environnement
- Clés API masquées dans l'interface
- Explorateur de dossiers restreint aux `browse_roots`
- Actions destructives avec confirmation HTMX

## État du projet
- [x] Module Config (CRUD, browse, test connexion)
- [x] Module Scan (filesystem, bases Radarr/Sonarr, orchestrateur async)
- [x] Module Résultats (liste, détail, actions statut)
- [x] Dashboard et statistiques de base
- [x] Actions de nettoyage réelles (DELETE API)
- [x] Filtres avancés sur la page résultats
- [x] Page de scan améliorée (options, confirmation 2 étapes)
- [x] Docker compose vérifié
- [x] Notifications Discord (webhook configurable, envoi scan + nettoyage)
- [x] Scans automatiques planifiés (intervalle configurable dans /config)
