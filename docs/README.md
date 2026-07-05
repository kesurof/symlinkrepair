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
```
