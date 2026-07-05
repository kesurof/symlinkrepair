# Sécurité

## Principes

- Simulation par défaut, jamais de nettoyage automatique
- Confirmation explicite en 2 étapes avant action destructive
- Aucun secret dans le code (clés API en config, jamais commitées)
- Les clés API sont masquées dans l'interface (`••••••••`)
- L'explorateur de dossiers est restreint aux `browse_roots` autorisés

## Explorateur de dossiers

`GET /api/browse?path=/mnt/media`

Contrôles :
- `Path(path).resolve()` pour éviter les `..` et symlinks malveillants
- Le chemin résolu doit commencer par l'un des `browse_roots` configurés
- Ne liste que les dossiers, pas les fichiers
- Ne remonte pas au-delà de `/`
- Configuration des racines autorisées dans `data/config.json`

## Clés API

- Stockées dans `data/config.json` (hors du repo via `.gitignore`)
- Jamais affichées en clair dans les templates
- Masquées dans l'interface : affichage `••••` + bouton "Afficher"
- Transmises en POST, jamais en GET (via les logs, referrer, etc.)

## Actions destructives

- Jamais lancées automatiquement
- Confirmation obligatoire (HTMX `hx-confirm` ou étape Alpine.js)
- Mode `dry-run` / simulation visible et explicite
- Limite de fichiers par défaut (configurable)
- Historique de toutes les actions en base

## Docker

- Conteneur isolé, pas d'accès root si possible
- Volumes montés en lecture seule pour les bibliothèques (si possible)
- Réseau interne pour accéder à Radarr/Sonarr
