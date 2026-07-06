---
name: screenshots
description: Capture d'écran des pages via Pageres CLI + Chromium
---

# screenshots

## Installation

```bash
# 1. Installer pageres-cli globalement
sudo npm install -g pageres-cli

# 2. Installer Chromium
sudo apt-get install -y chromium
```

## Configuration

La variable d'environnement `PUPPETEER_EXECUTABLE_PATH` doit pointer vers Chromium :

```bash
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

## Usage

### Script automatisé

```bash
# Lancer l'application (docker ou dev)
make dev

# Dans un autre terminal, lancer les captures
PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser bash scripts/screenshots.sh
```

Le script capture 5 pages :
- `http://localhost:8000` → `docs/screenshots/dashboard.png`
- `http://localhost:8000/scan` → `docs/screenshots/scan.png`
- `http://localhost:8000/results` → `docs/screenshots/results.png`
- `http://localhost:8000/reports` → `docs/screenshots/reports.png`
- `http://localhost:8000/config` → `docs/screenshots/config.png`

### Capture unique

```bash
PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser pageres \
  http://localhost:8000 1280x800 \
  --filename=docs/screenshots/ma-page.png
```

### Résolution

Les captures sont faites en **1280x800** (vue desktop).

## Format

- Fichiers : `PNG`
- Emplacement : `docs/screenshots/`
- Chaque fichier fait ~100-300 Ko
- Ils sont versionnés dans git (pour le README sur GitHub)

## Intégration README

```markdown
| Dashboard | Scan |
|---|---|
| ![dashboard](docs/screenshots/dashboard.png) | ![scan](docs/screenshots/scan.png) |
```

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `Could not find Chrome` | Chromium non trouvé | Vérifier `PUPPETEER_EXECUTABLE_PATH` |
| `Failed to launch the browser process` | Binaire corrompu | Réinstaller Chromium : `sudo apt-get install --reinstall chromium` |
| `E: dpkg a été interrompu` | APT bloqué | `sudo dpkg --configure -a` puis réessayer |
| `Command not found: pageres` | npm global pas dans le PATH | `sudo npm install -g pageres-cli` |
