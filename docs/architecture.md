# Architecture

## Stack

```
FastAPI + Jinja2 + HTMX 2.x + Alpine.js 3.x + Tailwind CSS (CDN) + SQLite + Docker
```

## Arborescence

```
app/
├── main.py                 # Point d'entrée, lifespan, routers
├── config.py               # Settings (env vars)
├── database.py             # SQLite, init_db, get_db
├── logging_config.py       # Logging structuré
├── error_handlers.py       # Gestion 404/500
├── routers/
│   ├── web.py              # Pages principales
│   ├── health.py           # Health check
│   ├── config.py           # Configuration API
│   ├── scan.py             # Lancement des scans
│   ├── results.py          # Résultats et détails
│   └── reports.py          # Rapports et stats
├── services/
│   ├── scanner.py          # Wrapper scripts Radarr/Sonarr
│   ├── radarr.py           # Appels API Radarr
│   └── sonarr.py           # Appels API Sonarr
├── models/
│   ├── scan.py             # Scan, Result
│   ├── config.py           # Paramètres applicatifs
│   └── report.py           # Rapport d'exécution
├── templates/
│   ├── base.html           # Layout global
│   ├── index.html          # Dashboard
│   ├── scan.html           # Page scan
│   ├── results.html        # Liste éléments
│   ├── detail.html         # Détail élément
│   ├── reports.html        # Rapports
│   ├── config.html         # Paramètres + explorateur dossiers
│   └── partials/           # Fragments HTMX
├── static/
│   └── css/
│       └── icons.svg       # Icônes SVG inline
├── services/
│   └── folder_browser.py   # Explorateur de dossiers sécurisé
```

## Flux type

1. Utilisateur clique "Lancer un scan" (HTMX)
2. `GET /scan/radarr` → `services/scanner.py` → script Radarr (subprocess)
3. Résultats parsés → stockés SQLite → rendus dans le template
4. Actions POST → confirmation → exécution → mise à jour fragment
