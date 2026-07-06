# Prochaines étapes

## Ce qui fonctionne

- [x] Configuration dynamique (CRUD config.json, browse sécurisé, test connexion)
- [x] Scan filesystem (parcours récursif, détection symlinks cassés, matching préfixes)
- [x] Import bases Radarr/Sonarr (docker cp + SQLite queries)
- [x] Orchestrateur async avec Lock (Radarr et Sonarr en parallèle)
- [x] Routes scan (POST déclenchement, stockage résultats en base)
- [x] Nettoyage réel : DELETE API Radarr/Sonarr, suppression symlink, refresh/search
- [x] Actions batch : Traiter (process), Marquer remplacé, Ignorer, Supprimer
- [x] Filtres page résultats : source, statut, saison, recherche texte
- [x] Pagination + filtres avancés (25/50/100 par page)
- [x] Déduplication des résultats (GROUP BY symlink_path + source)
- [x] Sélection multiple et actions batch
- [x] Page de scan avec options (mode, limite) + confirmation 2 étapes
- [x] Scan rapide éphémère (fastscan — filesystem only, sans persistance)
- [x] Rapports et statistiques de base
- [x] Dashboard avec stats temps réel (HTMX via OOB refresh)
- [x] Pages d'erreur (404, 500) avec fallback HTML/JSON
- [x] Interface mobile-friendly (cartes vs tableau)
- [x] Docker compose build + run vérifiés
- [x] Notifications Discord (webhook configurable, envoi scan + nettoyage)
- [x] Scans automatiques planifiés (intervalle configurable dans /config)
- [x] Vérificateur asynchrone (surveille les symlinks en attente de remplacement)

## Ce qu'il reste à faire

### 1. Tests automatisés

- Test du scan avec fichiers temporaires (tests d'intégration)
- Test de l'API config CRUD
- Test de l'explorateur de dossiers
- Mock des APIs Radarr/Sonarr pour tests unitaires
- Test des actions batch (process, fix, ignore, delete)
- Test de la déduplication (GROUP BY)

### 2. Sécurité

- Rate limiting sur les endpoints POST
- Validation renforcée des chemins dans l'explorateur
- Fichier de log avec rotation

### 3. Améliorations UX

- Mode sombre ?
- Tri des colonnes sur la page résultats
- Export CSV des résultats filtrés
- Historique des actions par résultat
