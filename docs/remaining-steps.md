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

### 1. Tests avec vraies APIs Radarr/Sonarr

Les endpoints DELETE API, refresh, search sont codés mais jamais testés
avec des instances réelles.

**Avant de pouvoir tester :**
- URL et clé API Radarr/Sonarr fonctionnelles
- Docker avec accès aux conteneurs Radarr/Sonarr (pour `docker cp`)
- Un bibliothèque avec au moins un symlink cassé vers un préfixe configuré

**Tests à faire :**
- `test_connection` → doit retourner version OK
- Scan + matching → doit trouver les vrais fichiers Radarr/Sonarr
- `POST /api/results/{id}/process` → DELETE API + refresh + search

### 2. Notifications Discord

- Webhook configuré dans l'interface
- Envoi automatique après scan/nettoyage
- Template de message personnalisable
- Activation/désactivation depuis les paramètres

### 3. Export TSV des résultats

- Lien vers le rapport TSV dans la page détail d'un scan
- Conservation des rapports dans `data/reports/`
- Colonnes : file_id, titre, chemin, cible, raison, statut HTTP

### 4. Statistiques temporelles

- Graphique d'évolution des symlinks cassés par jour
- Volume traité par semaine
- Taux de réussite des actions
- Derniers contenus corrigés / ignorés

### 5. Tests automatisés

- Test du scan avec fichiers temporaires (tests d'intégration)
- Test de l'API config CRUD
- Test de l'explorateur de dossiers
- Mock des APIs Radarr/Sonarr pour tests unitaires

### 6. Sécurité

- Rate limiting sur les endpoints POST
- Validation renforcée des chemins dans l'explorateur
- Fichier de log avec rotation

### 7. Améliorations UX

- Pagination sur la page résultats (>100 items)
- Filtre par saison pour Sonarr
- Édition des préfixes surveillés dans l'explorateur (actuellement juste sélection)
- Mode sombre ?

## Priorités

1. **Tests avec vraies APIs** — valider que tout le pipeline fonctionne en réel
2. **Notifications Discord** — feedback post-scan utile
3. **Export TSV** — trace écrite des actions

Si tu veux qu'on attaque un de ces points, fournis-moi les accès API
ou les spécifications complémentaires.
