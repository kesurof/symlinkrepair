# Prochaines étapes

## Ce qui fonctionne

- [x] Configuration dynamique (CRUD config.json, browse sécurisé, test connexion)
- [x] Scan filesystem (parcours récursif, détection symlinks cassés, matching préfixes)
- [x] Import bases Radarr/Sonarr (docker cp + SQLite queries)
- [x] Orchestrateur async avec Lock (Radarr et Sonarr en parallèle)
- [x] Routes scan (POST déclenchement, stockage résultats en base)
- [x] Routes résultats (liste, détail, ignorer, revérifier)
- [x] Rapports et statistiques de base
- [x] Dashboard avec stats temps réel (HTMX)
- [x] Pages d'erreur (404, 500) avec fallback HTML/JSON
- [x] Interface mobile-friendly (cartes vs tableau)

## Ce qu'il reste à faire

### 1. Actions de nettoyage réelles

Actuellement, les actions POST `/api/results/{id}/ignore` et `/recheck` changent
le statut en base. Il manque les actions destructives réelles :

- `POST /api/results/{id}/process` → DELETE API Radarr/Sonarr + suppression
  symlink local (optionnel) + refresh/search (optionnel)
- `POST /api/results/{id}/fix` → marquer comme corrigé manuellement
- `POST /api/scan/{source}/clean` → nettoyage réel en masse (déjà routé mais
  à tester avec API Radarr/Sonarr réelles)

### 2. Exécution avec vraies APIs

Les services `radarr.py` et `sonarr.py` sont codés mais pas testés avec des
instances Radarr/Sonarr réelles. À faire :

- Tester `test_connection` avec vraies URL + clé API
- Tester `copy_database` (docker cp) : nécessite Docker et conteneur Radarr/Sonarr
- Tester `delete_movie_file` / `delete_episode_file`
- Tester `refresh_movie` / `rescan_series`
- Tester `search_movies` / `search_season`

### 3. Filtres avancés sur la page résultats

- Filtre par source (Radarr/Sonarr)
- Filtre par statut (détecté, ignoré, corrigé)
- Filtre par texte (titre, chemin)
- Filtre par saison
- Pagination (si > 100 résultats)

### 4. Page de scan améliorée

- Options de filtre avant scan (tags, titre, limite, saison)
- Confirmation en 2 étapes pour le nettoyage réel (Alpine.js)
- Barre de progression pendant le scan (polling hx-trigger="every 2s")

### 5. Statistiques temporelles

- Graphique d'évolution des symlinks cassés
- Volume traité par semaine
- Taux de réussite des actions

### 6. Notifications Discord

- Webhook configuré dans l'interface
- Envoi automatique après scan/nettoyage
- Template Discord personnalisable

### 7. Export TSV des résultats

- Lien vers le rapport TSV dans la page détail
- Conservation des rapports dans `data/reports/`

### 8. Tests automatisés

- Test du scan avec fichiers temporaires (fait manuellement ci-dessus)
- Test de l'API Radarr/Sonarr mockée
- Test de la config CRUD
- Test de l'explorateur de dossiers

### 9. Docker

- Vérifier que `docker compose up --build` fonctionne
- Volume monté pour `data/` (config, DB)
- Volume monté pour les bibliothèques média (lecture seule)

### 10. Sécurité

- Rate limiting sur les endpoints POST
- Validation des chemins dans l'explorateur (déjà en place, mais à renforcer)
- CSRF token pour les actions destructives (HTMX n'envoie pas de CSRF par défaut)

## Priorités

1. **Actions de nettoyage** (le minimum pour que l'application soit utile)
2. **Tests avec vraies APIs** (validation du fonctionnement réel)
3. **Filtres page résultats** (utilisabilité au quotidien)
4. **Docker compose** (déploiement)
