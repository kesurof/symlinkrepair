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
│   ├── web.py              # Pages principales (dashboard, etc.)
│   ├── health.py           # Health check
│   ├── config_ui.py        # Page de configuration HTML
│   ├── scan.py             # Lancement et suivi des scans
│   ├── results.py          # Résultats et détail
│   └── reports.py          # Rapports et stats
├── services/
│   ├── scanner.py          # Orchestrateur de scan (lock, lifecycle)
│   ├── radarr.py           # Client API Radarr + DB loader
│   ├── sonarr.py           # Client API Sonarr + DB loader
│   ├── filescanner.py      # Scan filesystem (symlinks detection)
│   └── config_service.py   # CRUD config.json + browse sécurisé
├── models/
│   ├── scan.py             # Scan state, ScanTarget
│   ├── config.py           # Config Pydantic model
│   └── report.py           # Rapport d'exécution
├── templates/
│   ├── base.html           # Layout global (nav, header, footer)
│   ├── index.html          # Dashboard
│   ├── scan.html           # Page scan
│   ├── results.html        # Liste éléments
│   ├── detail.html         # Détail élément
│   ├── reports.html        # Rapports
│   ├── config.html         # Configuration + explorateur dossiers
│   └── partials/           # Fragments HTMX
│       ├── scan_status.html
│       ├── result_card.html
│       ├── result_table.html
│       ├── folder_browser.html
│       └── stats_widget.html
└── static/
    └── css/
        └── icons.svg       # Icônes SVG inline
```

## Cycle de vie d'un scan (async)

```
┌─────────────────────────────────────────────────┐
│                   États                          │
│                                                  │
│  idle ──→ running ──→ completed                  │
│                │                                  │
│                └──→ error                        │
│                                                  │
│  running + idem pour l'autre source = OK         │
│  (Radarr et Sonarr peuvent tourner en //)        │
│  running + même source = refusé (Lock)           │
└─────────────────────────────────────────────────┘
```

Le scan s'exécute dans un `asyncio.create_task` (pas de thread). Le frontend
interroge `GET /scan/{id}/status` toutes les 2s via `hx-trigger="every 2s"`.

## Flux type

### Scan
1. `POST /scan/radarr` → création du scan en DB (`status=running`)
2. Lancement d'un task asynchrone qui exécute le scan
3. Le frontend poll `GET /scan/{id}/status` toutes les 2s (fragment HTMX)
4. À la fin : DB update (`status=completed`), insertion des `results`
5. Le frontend affiche le résumé et redirige vers `/results?scan_id=X`

### Configuration
1. `GET /config` → page HTML avec le formulaire
2. Alpine.js gère l'état local (champs, explorateur)
3. `POST /api/config` → sauvegarde dans `data/config.json`
4. `GET /api/browse?path=...` → explorateur de dossiers sécurisé

### Action sur un résultat
1. `POST /results/{id}/fix` → confirmation → mise à jour du statut
2. Si réel : appel API Radarr/Sonarr, suppression symlink local (optionnel)
3. Mise à jour du fragment HTMX pour refléter le nouveau statut

## Services

| Service | Rôle |
|---------|------|
| `config_service.py` | Lire/écrire `data/config.json`, valider, browse sécurisé |
| `filescanner.py` | Parcourir les LIBRARY_ROOTS, détecter symlinks, vérifier cibles |
| `radarr.py` | Appels API Radarr + copie DB + chargement MovieFiles |
| `sonarr.py` | Appels API Sonarr + copie DB + chargement EpisodeFiles |
| `scanner.py` | Orchestrateur : lock, lancement async, lifecycle, matching |

## Routage

| Router | Routes | Format |
|--------|--------|--------|
| `web.py` | `/` (dashboard) | HTML |
| `config_ui.py` | `/config` | HTML + fragments |
| `scan.py` | `/scan`, `/scan/{source}`, `/scan/{id}/status` | HTML + JSON |
| `results.py` | `/results`, `/results/{id}`, `/results/{id}/action` | HTML + JSON |
| `reports.py` | `/reports`, `/api/stats` | HTML + JSON |
| `config_service.py` (routier) | `/api/config`, `/api/browse`, `/api/config/test-*` | JSON |
| `health.py` | `/health` | JSON |
