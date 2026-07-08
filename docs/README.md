# Documentation SymlinkRepair

```
docs/
├── README.md               ← Ce fichier
├── specification.md        ← Spécification fonctionnelle complète
├── architecture.md         ← Architecture technique
├── configuration.md        ← Configuration dynamique + explorateur de dossiers
├── api.md                  ← Référence des endpoints
├── database.md             ← Schéma et accès BDD
├── frontend.md             ← Organisation des pages et composants
├── redesign-ui.md          ← Refonte UI (sidebar + bottom nav + dark mode)
├── security.md             ← Modèle de sécurité
├── screenshots/
│   ├── dashboard.png       ← Dashboard
│   ├── results.png         ← Liste des résultats
│   ├── scan.png            ← Page de scan
│   ├── reports.png         ← Historique des scans
│   ├── season_detail.png   ← Détail d'une saison
│   └── result_detail.png   ← Détail d'un fichier
├── scripts/
│   ├── radarr_cleanup.md   ← Script Radarr existant
│   └── sonarr_cleanup.md   ← Script Sonarr existant
└── vibecoding.md           ← Guide développement assisté par IA
```

## Résumé

SymlinkRepair détecte, analyse et traite les symlinks cassés pointant vers
AllDebrid / Decypharr dans les bibliothèques Radarr et Sonarr.

## Quick start

```bash
make dev        # Lancer en dev (uvicorn --reload) sur http://localhost:8000
make dev-docker # Lancer en dev avec Docker (build local + --reload)
make test       # Lancer les tests
make docker     # Lancer avec Docker (image ghcr pré-buildée)
make deploy     # Pusher le code sur GitHub (sans build Docker)
```

## Docker Compose — développement local

`docker-compose.dev.yml` est versionné dans git pour le développement.  
Il build l'image localement et monte le code source (`./app:/app/app`) pour que `--reload` fonctionne.

**Prérequis** : le réseau Docker externe `traefik_proxy` doit exister.

```bash
make dev-docker
# ou
docker compose -f docker-compose.dev.yml up --build
```

| Particularité | Prod (`docker-compose.yml`) | Dev (`docker-compose.dev.yml`) |
|---|---|---|
| Image | `ghcr.io/...` (pré-buildée) | Build local |
| Rechargement auto | Non | Oui (`--reload`) |
| Restart auto | `unless-stopped` | Non |
| Healthcheck | Oui (`/health`) | Non |
| Réseau traefik | Non | Oui (externe `traefik_proxy`) |
| Montage `/home` | Non | Oui |
| Versionné dans git | Oui | Oui |

## Publier une nouvelle version

Le build de l'image Docker est déclenché manuellement depuis GitHub.

```bash
# Pusher le code
git add . && git commit -m "..."
make deploy    # git push origin main
```

Puis sur GitHub :
1. Aller sur **Actions** → **Docker Publish** → **Run workflow**
2. Rentrer la version (ex: `0.3.0`)
3. Cliquer **Run workflow**

Le CI build l'image et la pousse sur `ghcr.io/kesurof/symlinkrepair` avec les tags `v0.3.0` et `latest`.

**Note** : pousser sur `main` ne build plus d'image. Le build est uniquement manuel via *workflow_dispatch*.
