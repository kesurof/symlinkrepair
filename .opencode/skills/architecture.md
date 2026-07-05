---
name: architecture
description: Conventions de code et structure du projet
---

# architecture

## Structure

```
app/
├── main.py           # Point d'entrée FastAPI, lifespan, inclusion des routers
├── config.py         # Settings via variables d'environnement
├── database.py       # Connexion SQLite, init_db, get_db
├── logging_config.py # Configuration du logging structuré
├── error_handlers.py # Gestionnaires d'erreurs (404, 500)
├── routers/          # Routes FastAPI
├── services/         # Logique métier
├── models/           # Modèles Pydantic
├── templates/        # Templates Jinja2
└── static/           # Fichiers statiques (optionnel)
```

## Conventions

- **Langue** : code en anglais (variables, fonctions, commentaires), templates et messages utilisateur en français
- **Imports** : toujours utiliser le chemin absolu depuis `app.` (ex: `from app.services.scanner import scan_directory`)
- **Typage** : typer les paramètres et retours des fonctions (mypy check)
- **Routers** : un fichier par domaine fonctionnel, préfixe explicite
- **Services** : pas d'appel à la DB ou aux templates, pure logique métier
- **Modèles Pydantic** : utilisés pour la validation et la sérialisation, pas d'ORM
- **Erreurs** : utiliser `HTTPException` de FastAPI pour les erreurs métier, ou laisser les handlers globaux gérer
- **Dépendances** : uniquement dans `pyproject.toml`, pas de requirements.txt
