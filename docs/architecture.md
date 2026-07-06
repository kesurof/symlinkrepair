# Architecture

## Stack

```
FastAPI + Jinja2 + HTMX 2.x + Alpine.js 3.x + Tailwind CSS (CDN) + Inter + SQLite + Docker
```

## Arborescence

```
app/
├── main.py                 # Point d'entrée, lifespan, routers
├── config.py               # Settings (env vars)
├── database.py             # SQLite, init_db, get_db
├── templates.py            # Instance Jinja2Templates partagée
├── logging_config.py       # Logging structuré
├── error_handlers.py       # Gestion 404/500
├── routers/
│   ├── web.py              # Dashboard (/)
│   ├── health.py           # Health check (/health)
│   ├── config_ui.py        # Page de configuration HTML (/config)
│   ├── scan.py             # Scans (/scan, /fastscan → 301, /api/scan/*)
│   ├── results.py          # Résultats (/results, /api/results/*)
│   ├── reports.py          # Rapports (/reports, /api/stats)
│   └── api_config.py       # API config (/api/config, /api/browse)
├── services/
│   ├── scanner.py          # Orchestrateur de scan (lock, lifecycle)
│   ├── filescanner.py      # Scan filesystem (détection symlinks)
│   ├── radarr.py           # Client API Radarr + DB loader
│   ├── sonarr.py           # Client API Sonarr + DB loader
│   ├── cleanup.py          # Actions de nettoyage (DELETE API, refresh, search)
│   ├── verifier.py         # Vérificateur asynchrone (surveille remplacement)
│   ├── scheduler.py        # Scans automatiques planifiés
│   ├── discord.py          # Notifications Discord (webhook)
│   └── config_service.py   # CRUD config.json + browse sécurisé
├── models/
│   ├── config.py           # Config Pydantic model
│   └── scan.py             # Scan state, Result
├── templates/
│   ├── base.html           # Layout : sidebar desktop + bottom nav mobile
│   ├── index.html          # Dashboard
│   ├── scan.html           # Page scan (complet + rapide fusionnés)
│   ├── results.html        # Liste résultats
│   ├── detail.html         # Détail élément
│   ├── reports.html        # Rapports
│   ├── config.html         # Configuration + explorateur dossiers
│   ├── error.html          # Page d'erreur générique (étend base.html)
│   ├── 404.html            # Page non trouvée (étend base.html)
│   └── partials/
│       ├── results_content.html  # Tableau/cards résultats (swap HTMX)
│       └── reports_content.html  # Tableau/cards rapports (swap HTMX)
└── static/
    ├── htmx.min.js         # HTMX 2.x
    ├── alpine.min.js       # Alpine.js 3.x
    └── app.css             # Animations CSS (fade, slide-up, skeleton)
```

## Cycle de vie d'un scan

```
1. Validation config (library_roots, target_prefixes, api_key)
2. Scan filesystem (iter_symlinks + inspect_symlink)
3. Copie DB conteneurs (docker cp)
4. Chargement MovieFiles / EpisodeFiles
5. Matching : symlink_path → record Radarr/Sonarr
6. Enrichissement : titre, saison, tags, ids
7. Insertion en base (scans + results)
8. Si mode=clean : process_all_detected (DELETE API)
9. Notification Discord
```

## Services

| Service | Rôle |
|---------|------|
| `filescanner.py` | Parcourir les `library_roots`, détecter symlinks, vérifier cibles |
| `radarr.py` | Appels API Radarr + copie DB + chargement MovieFiles |
| `sonarr.py` | Appels API Sonarr + copie DB + chargement EpisodeFiles |
| `scanner.py` | Orchestrateur : lock, lancement async, lifecycle, matching |
| `cleanup.py` | Nettoyage réel : DELETE API, suppression symlink, refresh, search |
| `verifier.py` | Surveillance asynchrone : vérifie si les symlinks sont remplacés |
| `scheduler.py` | Scans automatiques planifiés à intervalle configurable |
| `discord.py` | Notifications via webhook Discord |
| `config_service.py` | Lire/écrire `data/config.json`, valider, browse sécurisé |

## Routage

| Router | Routes | Format |
|--------|--------|--------|
| `web.py` | `/` | HTML |
| `config_ui.py` | `/config` | HTML + fragments |
| `scan.py` | `/scan`, `/fastscan` (→ 301), `/api/scan/*`, `/api/fast-scan` | HTML + JSON |
| `results.py` | `/results`, `/results/{id}`, `/api/results/*` | HTML + JSON |
| `reports.py` | `/reports`, `/api/stats`, `/api/scans/delete` | HTML + JSON |
| `api_config.py` | `/api/config`, `/api/browse`, `/api/config/test-*` | JSON |
| `health.py` | `/health` | JSON |

## Design UI

- **Layout** : sidebar desktop rétractable (`w-56` / `w-16`) + bottom nav mobile (5 onglets)
- **Dark mode** : classe `dark` sur `<html>`, persisté en localStorage
- **Font** : Inter (Google Fonts CDN)
- **Palette brand** : indigo (`brand-50` à `brand-900`)
- **Icônes** : Heroicons SVG inline
- **Animations** : définies dans `app/static/app.css` (fade-in, slide-up, skeleton)
