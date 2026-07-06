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
├── templates.py      # Instance Jinja2Templates partagée
├── logging_config.py # Configuration du logging structuré
├── error_handlers.py # Gestionnaires d'erreurs (404, 500)
├── routers/          # Routes FastAPI (domaines fonctionnels)
│   ├── web.py           # Dashboard (/)
│   ├── health.py        # Health check (/health)
│   ├── config_ui.py     # Configuration HTML (/config)
│   ├── scan.py          # Scans (/scan, /api/scan/*, /api/fast-scan)
│   ├── results.py       # Résultats (/results, /api/results/*)
│   ├── reports.py       # Rapports (/reports, /api/stats)
│   └── api_config.py    # API config (/api/config, /api/browse)
├── services/         # Logique métier
│   ├── scanner.py        # Orchestrateur de scan (lock, lifecycle)
│   ├── filescanner.py    # Scan filesystem (détection symlinks)
│   ├── radarr.py         # Client API Radarr + DB loader
│   ├── sonarr.py         # Client API Sonarr + DB loader
│   ├── cleanup.py        # Actions de nettoyage (DELETE API, refresh, search)
│   ├── verifier.py       # Vérificateur asynchrone
│   ├── scheduler.py      # Scans automatiques planifiés
│   ├── discord.py        # Notifications Discord
│   └── config_service.py # CRUD config.json + browse sécurisé
├── models/           # Modèles Pydantic
│   ├── config.py         # AppConfig, RadarrConfig, SonarrConfig...
│   └── scan.py           # Scan, Result
├── templates/        # Templates Jinja2
│   ├── base.html         # Layout : sidebar desktop + bottom nav mobile
│   ├── index.html        # Dashboard
│   ├── scan.html         # Page scan (complet + rapide fusionnés)
│   ├── results.html      # Liste résultats
│   ├── detail.html       # Détail élément
│   ├── reports.html      # Rapports
│   ├── config.html       # Configuration
│   ├── error.html        # Erreur générique (étend base.html)
│   ├── 404.html          # Page non trouvée (étend base.html)
│   └── partials/
│       ├── results_content.html  # Tableau/cards résultats (swap HTMX)
│       └── reports_content.html  # Tableau/cards rapports (swap HTMX)
├── static/
│   ├── htmx.min.js       # HTMX 2.x
│   ├── alpine.min.js     # Alpine.js 3.x
│   └── app.css           # Animations CSS (fade, slide-up, skeleton)
```

## Conventions

- **Langue** : code en anglais (variables, fonctions), templates et messages utilisateur en français
- **Imports** : toujours utiliser le chemin absolu depuis `app.` (ex: `from app.services.scanner import start_scan`)
- **Typage** : typer les paramètres et retours des fonctions
- **Routers** : un fichier par domaine fonctionnel
- **Services** : pas d'appel direct à la DB ou aux templates
- **Modèles Pydantic** : validation et sérialisation, pas d'ORM
- **Erreurs** : utiliser `HTTPException` de FastAPI, ou handlers globaux
- **Dépendances** : uniquement dans `pyproject.toml`, pas de requirements.txt

## Routes

| Router | Routes | Format |
|--------|--------|--------|
| `web.py` | `/` | HTML |
| `health.py` | `/health` | JSON |
| `config_ui.py` | `/config` | HTML |
| `scan.py` | `/scan`, `/fastscan` (→ 301), `/api/scan/*`, `/api/fast-scan` | HTML + JSON |
| `results.py` | `/results`, `/results/{id}`, `/api/results/*` | HTML + JSON |
| `reports.py` | `/reports`, `/api/stats`, `/api/scans/delete` | HTML + JSON |
| `api_config.py` | `/api/config`, `/api/browse`, `/api/config/test-*` | JSON |

## Services

| Service | Rôle |
|---------|------|
| `filescanner.py` | Parcourir les `library_roots`, détecter symlinks, vérifier cibles |
| `radarr.py` | Appels API Radarr + copie DB + chargement MovieFiles |
| `sonarr.py` | Appels API Sonarr + copie DB + chargement EpisodeFiles |
| `scanner.py` | Orchestrateur : lock, lifecycle, matching |
| `cleanup.py` | Nettoyage réel : DELETE API, suppression symlink, refresh, search |
| `verifier.py` | Surveillance asynchrone (remplacement des symlinks) |
| `scheduler.py` | Scans automatiques planifiés |
| `discord.py` | Notifications via webhook Discord |
| `config_service.py` | CRUD config.json + browse sécurisé |

## Règles

- Les endpoints qui retournent du HTML pour HTMX doivent détecter `HX-Request` header
- Ne PAS utiliser Alpine pour stocker l'état serveur — utiliser `data-*` attributes + OOB
- Les templates Jinja2 reçoivent toujours `request` automatiquement (Starlette)
- Layout : sidebar desktop rétractable (`w-56` / `w-16`) + bottom nav mobile 5 onglets
- Dark mode : classe `dark` sur `<html>`, persisté localStorage, Inter font, palette indigo
