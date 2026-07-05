# Prochaines étapes

## Ce qui fonctionne

- [x] Configuration dynamique (CRUD config.json, browse sécurisé, test connexion)
- [x] Scan filesystem (parcours récursif, détection symlinks cassés, matching préfixes)
- [x] Import bases Radarr/Sonarr (docker cp + SQLite queries)
- [x] Orchestrateur async avec Lock (Radarr et Sonarr en parallèle)
- [x] Routes scan (POST déclenchement, stockage résultats en base)
- [x] Actions de nettoyage : DELETE API, suppression symlink, refresh/search
- [x] Actions : marquer corrigé, ignorer, revérifier
- [x] Filtres page résultats : source, statut, recherche texte
- [x] Page de scan avec options (mode, limite) + confirmation 2 étapes
- [x] Rapports et statistiques de base
- [x] Dashboard avec stats temps réel (HTMX)
- [x] Pages d'erreur (404, 500) avec fallback HTML/JSON
- [x] Interface mobile-friendly (cartes vs tableau)
- [x] Docker compose build + run vérifiés

## Ce qu'il reste à faire

### 1. Tests automatisés

- Test du scan avec fichiers temporaires (tests d'intégration)
- Test de l'API config CRUD
- Test de l'explorateur de dossiers
- Mock des APIs Radarr/Sonarr pour tests unitaires

### 2. Sécurité

- Rate limiting sur les endpoints POST
- Validation renforcée des chemins dans l'explorateur
- Fichier de log avec rotation

### 3. Améliorations UX

- Pagination sur la page résultats (>100 items)
- Filtre par saison pour Sonarr
- Édition des préfixes surveillés dans l'explorateur (actuellement juste sélection)
- Mode sombre ?
