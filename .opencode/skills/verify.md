---
name: verify
description: Vérification systématique avant chaque commit ou PR. Utilise aussi quand l'utilisateur demande de tester, vérifier, valider le code, lancer les tests, faire un check, une revue ou un audit du code.
---

# verify

Utilise ce skill avant chaque commit, PR, ou quand l'utilisateur demande une vérification de l'ensemble du code.

## Commande full-check (tout-en-un)

Exécute cette commande pour lancer tous les tests automatisés d'un coup :

```bash
make format && make lint && make test
```

Puis charge aussi le skill `coherence` et exécute les vérifications de documentation et cohérence listées ci-dessous.

## Checks automatisés obligatoires

```bash
make format    # ruff format (formate le code automatiquement)
make lint      # ruff check (lint + vérification des imports)
make test      # pytest -v (tests unitaires)
```

## Vérifications manuelles — à parcourir après les checks auto

### Code Python
- [ ] Pas de `print()` ou `breakpoint()` laissé dans le code
- [ ] Pas de commentaire superflu ou de code commenté
- [ ] Pas de secret, token ou chemin absolu en dur
- [ ] Les imports sont triés (vérifié par `make lint`)
- [ ] Les noms de variables/fonctions sont en anglais et explicites
- [ ] Les routes FastAPI ont un type de retour explicite (`response_class`)
- [ ] Les endpoints gèrent les erreurs (try/except ou HTTPException)

### Patterns projet
- [ ] Les endpoints HTMX détectent bien `request.headers.get("hx-request") == "true"`
- [ ] Les données serveur sont dans `data-*` attributes, pas dans Alpine `x-text`
- [ ] Les OOB swaps (`hx-swap-oob="true"`) sont en fin de partial
- [ ] Les mutations DB sont suivies de `await db.commit()`
- [ ] Les requêtes SQL utilisent des paramètres `?` (pas de f-string pour les valeurs)
- [ ] Les actions destructives ont une confirmation (modale Alpine ou `hx-confirm`)
- [ ] Les classes `dark:` sont ajoutées sur chaque élément (dark mode)
- [ ] Les pages ont un layout mobile (bottom nav + cards) et desktop (sidebar + table)
- [ ] Les nouvelles pages étendent `base.html` (pas de page HTML standalone sauf erreur/404)
- [ ] Les modales de confirmation utilisent `slide-up` + `items-end md:items-center` (responsive)
- [ ] Les statuts des résultats utilisent le pattern pastille (dot `w-1.5 h-1.5 rounded-full` + texte)

### Cohérence documentation
- [ ] Les actions batch du code sont documentées dans `AGENTS.md`, `.opencode/skills/frontend.md`, `.opencode/skills/db.md`
- [ ] Les valeurs `action` de la table `results` sont documentées dans `AGENTS.md`
- [ ] Les routes FastAPI sont listées dans `AGENTS.md` et `docs/api.md`

## Procédure complète

1. Lancer `make format && make lint && make test`
2. Charger le skill `coherence` et exécuter ses vérifications automatiques
3. Parcourir la checklist manuelle ci-dessus
4. Si tout est vert, la tâche peut être déclarée terminée

## Si un check échoue

1. Lire l'erreur attentivement
2. Corriger le problème
3. Relancer `make format && make lint && make test`
4. Ne pas déclarer terminé tant que tout n'est pas vert
