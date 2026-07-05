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
- [ ] Les imports sont triés (ruff s'en charge, mais vérifier)
- [ ] Les noms de variables/fonctions sont en anglais et explicites
- [ ] Les templates Jinja2 utilisent des noms de variables clairs
- [ ] Les routes FastAPI ont un type de retour explicite (`response_class`)
- [ ] Les endpoints gèrent les erreurs (try/except ou HTTPException)

## Si un check échoue

1. Lire l'erreur attentivement
2. Corriger le problème
3. Relancer le check
4. Ne pas commit tant que tout n'est pas vert
