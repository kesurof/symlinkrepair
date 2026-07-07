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
make deploy     # Pusher le code sur GitHub (sans build Docker)
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
