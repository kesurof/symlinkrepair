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

## Commandes
```bash
# Lancer en dev
uvicorn app.main:app --reload --port 8000

# Lint
ruff check .

# Lancer avec Docker
docker compose up --build
```

## Base de données
- Fichier SQLite dans `data/symlinkrepair.db` (ignoré par git)
- Initialisation automatique au démarrage via `app/database.py`
- Tables : `scans`, `results`

## Sécurité
- Aucun secret dans le code
- Configuration via variables d'environnement
- Pas de données sensibles dans les templates
