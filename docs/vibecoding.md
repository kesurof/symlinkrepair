# Guide développement assisté par IA (vibecoding)

## Workflow recommandé

1. **Charger le skill `architecture`** → comprendre la structure
2. **Consulter `docs/specification.md`** → scope, V1 items
3. **Consulter `docs/configuration.md`** → si tu touches aux paths/config
4. **Charger le skill `db`** → si tu touches à la base
5. **Charger le skill `frontend`** → si tu touches aux templates
6. **Écrire le code** en respectant les conventions
7. **Charger le skill `verify`** → avant de commit
8. **Exécuter `make lint && make test`** → validation finale

## Règles d'or

- **Ne jamais inventer une API** : si tu as besoin d'un endpoint Radarr/Sonarr,
  vérifie d'abord dans les scripts existants (`docs/scripts/`)
- **Ne jamais dupliquer la config** : les chemins et clés API sont dans
  `data/config.json`, pas en dur dans le code
- **Ne jamais exposer de secret** : les clés API sont masquées dans l'interface
- **Toute action destructive passe par une confirmation** : pas de `POST` sans
  `hx-confirm` ou étape Alpine.js
- **Un changement de schéma DB = une modification de `app/database.py`**
- **Les templates Jinja2 n'ont pas accès aux objets Python** : tout doit être
  passé explicitement dans le contexte

## Questions à se poser avant d'écrire du code

1. Est-ce dans le scope V1 ? (sinon, le noter et passer)
2. Est-ce que ça casse la base existante ?
3. Est-ce que ça introduit une dépendance ? (si oui, la justifier)
4. Est-ce que ça marche sur mobile ?
5. Est-ce que l'action est réversible / tracée ?
