---
name: verify
description: Vérification systématique avant chaque commit ou PR
---

# verify

Utilise ce skill avant chaque commit ou avant de déclarer une tâche terminée.

## Checks obligatoires

```bash
make lint      # ruff check
make format    # ruff format
make test      # pytest -v
```

## Vérifications manuelles

- [ ] Pas de `print()` ou `breakpoint()` laissé dans le code
- [ ] Pas de commentaire superflu ou de code commenté
- [ ] Pas de secret, token ou chemin absolu en dur
- [ ] Les imports sont triés (ruff s'en charge)
- [ ] Les noms de variables/fonctions sont en anglais et explicites
- [ ] Les templates Jinja2 utilisent des noms de variables clairs
- [ ] Les routes FastAPI ont un type de retour explicite (`response_class`)
- [ ] Les endpoints gèrent les erreurs (try/except ou HTTPException)

## Vérifications spécifiques au projet

- [ ] Les endpoints HTMX détectent bien `request.headers.get("hx-request") == "true"`
- [ ] Les données serveur sont dans `data-*` attributes, pas dans Alpine `x-text`
- [ ] Les OOB swaps (`hx-swap-oob="true"`) sont en fin de partial
- [ ] Les mutations DB sont suivies de `await db.commit()`
- [ ] Les requêtes SQL utilisent des paramètres `?` (pas de f-string pour les valeurs)
- [ ] Les actions destructives ont une confirmation (modale Alpine ou `hx-confirm`)

## Si un check échoue

1. Lire l'erreur attentivement
2. Corriger le problème
3. Relancer le check
4. Ne pas commit tant que tout n'est pas vert
