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
make dev        # Lancer en dev sur http://localhost:8000
make test       # Lancer les tests
make docker     # Lancer avec Docker
make push       # Pusher sur GitHub → CI build & push l'image Docker multi-arch
```

## Docker Compose — développement local

Un fichier `docker-compose.dev.yml` (ignoré par git) est disponible en local.
Il correspond à l'ancienne configuration avec réseau traefik et montage `/home/...` :

```bash
docker compose -f docker-compose.dev.yml up --build
```

Relancer localement avec build

```bash
docker compose down 2>&1 && docker compose -f docker-compose.dev.yml up --build 2>&1
```

| Particularité | Prod (`docker-compose.yml`) | Dev (`docker-compose.dev.yml`) |
|---|---|---|
| Restart auto | `unless-stopped` | Non |
| Healthcheck | Oui (`/health`) | Non |
| Fichier `.env` | Charge `.env` | Non |
| Réseau traefik | Non | Oui (externe) |
| Montage `/home/...` | Non (commenté) | Oui |
| Versionné dans git | Oui | Non (`.gitignore`) |

## Publier une nouvelle version

La publication de l'image Docker est automatisée via GitHub Actions.
Un simple push sur `main` déclenche le build multi-arch (amd64 + arm64)
et la publication sur `ghcr.io/kesurof/symlinkrepair`.

```bash
# 1. Pusher la dernière version
git add . && git commit -m "..."
git push origin main

# 2. (Optionnel) Créer un tag de version pour marquer une release
git tag v0.2.0
make push    # equivalent à : git push origin main && git push origin --tags
```

La CI :
- Build les images **linux/amd64** et **linux/arm64**
- Les pousse sur **ghcr.io** avec les tags `latest`, `main`, `v*`, `sha-<commit>`
- Utilise le cache GitHub Actions pour accélérer les builds suivants
