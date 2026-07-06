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

`détecté` → `recherche` → `en_attente` → `remplacé` / `non_remplacé` / `ignoré` / `échoué`

| Statut | Description |
|--------|-------------|
| `détecté` | Détecté par un scan, en attente d'action |
| `recherche` | En cours de revérification |
| `en_attente` | DELETE API envoyé, en attente de confirmation |
| `remplacé` | Symlink remplacé ou marqué manuellement comme corrigé |
| `non_remplacé` | Vérifié : le symlink n'a pas été remplacé |
| `ignoré` | Ignoré par l'utilisateur |
| `échoué` | L'action API a échoué |

### Actions disponibles

| Action | Effet | Statut résultant |
|--------|-------|------------------|
| **Traiter** | DELETE API Radarr/Sonarr + recherche | `en_attente` |
| **Marquer corrigé** | Flag manuel | `remplacé` |
| **Ignorer** | Cache le résultat | `ignoré` |
| **Revérifier** | Remet en file d'attente | `recherche` |
| **Supprimer** | Supprime la ligne en base | — |

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

