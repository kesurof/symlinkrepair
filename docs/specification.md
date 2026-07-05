# Spécification fonctionnelle

> Vision produit : centre de contrôle simple pour réparer les liens médias cassés.
> Trois questions : Qu'est-ce qui est cassé ? Pourquoi ? Quelle action sûre ?

## Blocs fonctionnels

### 1. Détection
Scan des bibliothèques via les scripts Radarr/Sonarr en mode simulation.
Photographie instantanée des symlinks cassés, fichiers concernés, raisons.

### 2. Analyse
Vue organisée par application (Radarr/Sonarr), film, série, saison.
Compteurs, historique, évolution temporelle.

### 3. Recherche
Filtrage par titre, chemin, tag, saison. Résultats instantanés.

### 4. Action
Simulation ou nettoyage réel, avec confirmation explicite.
Par élément, sélection, film, série ou saison entière.

## Pages

| Page | Rôle |
|------|------|
| Dashboard | Vue synthétique, statuts, compteurs globaux |
| Scan | Lancement et suivi des analyses |
| Éléments | Liste des fichiers problématiques (tableau + cartes mobile) |
| Détail | Infos complètes d'un élément + actions |
| Rapports | Historique des traitements |
| Paramètres | Configuration Radarr/Sonarr + explorateur de dossiers |

## Statuts des éléments

`detected` → `pending` → `processed` / `fixed` / `ignored` / `error` / `recheck_needed`

## V1 (14 items)

1. Configuration Radarr/Sonarr
2. Test API Radarr/Sonarr
3. Scan Radarr
4. Scan Sonarr
5. Affichage des résultats
6. Recherche par mots-clés
7. Filtres simples
8. Détail d'un élément
9. Simulation depuis l'interface
10. Nettoyage réel avec confirmation
11. Historique des scans
12. Statistiques essentielles
13. Rapports consultables
14. Interface mobile friendly

