---
name: coherence
description: Vérifie la cohérence entre le code et la documentation avant commit
---

# coherence

Charge ce skill avant chaque commit ou PR pour t'assurer que toute modification
du code a son équivalent dans la documentation et vice versa.

## Utilisation

```bash
/skill coherence
```

Puis parcourir la checklist et exécuter les commandes de vérification.

---

## 1 — Arborescence

### Vérification manuelle

- [ ] Tout fichier nouveau dans `app/` est listé dans :
  - `AGENTS.md` (section Stack ou État du projet)
  - `docs/architecture.md` (arborescence)
  - `.opencode/skills/architecture.md` (arborescence)
- [ ] Tout fichier supprimé de `app/` est retiré des 3 listes ci-dessus
- [ ] Les templates Jinja2 dans `app/templates/` sont listés dans `docs/frontend.md`
- [ ] Les services dans `app/services/` sont listés dans `docs/architecture.md`

### Commande automatique

```bash
# Vérifie que chaque fichier .py dans app/ a une entrée dans architecture.md
for f in $(find app -name '*.py' -not -name '__init__.py' | sort); do
  name=$(basename "$f" .py)
  if ! grep -q "$name" docs/architecture.md 2>/dev/null; then
    echo "❌ $name manque dans docs/architecture.md"
  fi
done
```

---

## 2 — Endpoints

### Vérification manuelle

- [ ] Tout nouveau endpoint FastAPI a sa ligne dans :
  - `docs/api.md` (tableau par catégorie)
  - `AGENTS.md` (section Endpoints)
- [ ] Tout endpoint supprimé est retiré des 2 docs
- [ ] Les méthodes (GET/POST) et chemins correspondent exactement

### Commande automatique

```bash
# Extrait les routes du code
echo "=== ROUTES CODE ==="
python3 << 'PYEOF' | sort > /tmp/routes_code.txt
import re, subprocess
r = subprocess.run(['grep','-rn','@router.','app/routers/'], capture_output=True, text=True)
for line in r.stdout.splitlines():
    m = re.search(r'@router\.(get|post|put|delete)\s*\(\s*["\x27]([^"\x27]+)["\x27]', line)
    if m: print(f'{m.group(1).upper()} {m.group(2)}')
PYEOF

# Extrait les routes de AGENTS.md
grep -E '^- `(GET|POST|PUT|DELETE) ' AGENTS.md \
  | sed 's/- `//; s/`.*//' | sort > /tmp/routes_agents.txt
echo "=== Diff AGENTS.md ==="
comm -13 /tmp/routes_agents.txt /tmp/routes_code.txt | sed 's/^/❌ Manque dans AGENTS.md: /'

# Extrait les routes de docs/api.md (lignes commençant par "| GET |", "| POST |", etc.)
grep -E '^\| (GET|POST|PUT|DELETE) ' docs/api.md \
  | sed 's/^| \(GET\|POST\|PUT\|DELETE\) | `\([^`]*\)`.*/\1 \2/' | sort > /tmp/routes_api.txt
echo "=== Diff api.md ==="
comm -13 /tmp/routes_api.txt /tmp/routes_code.txt | sed 's/^/❌ Manque dans api.md: /'
comm -23 /tmp/routes_api.txt /tmp/routes_code.txt | sed 's/^/⚠️  Dans api.md mais pas dans le code: /'
```

---

## 3 — Statuts (results.status)

### Vérification manuelle

- [ ] Tout statut utilisé dans le code figure dans les tableaux de statuts de :
  - `AGENTS.md` (section Statuts)
  - `docs/database.md`
  - `.opencode/skills/db.md`
- [ ] Les statuts obsolètes (`réparé`, `processed`, etc.) sont gérés par migration dans `database.py`

### Commande automatique

```bash
echo "=== STATUS IN CODE (excluding 'réparé' legacy migration) ==="
(
  grep -roh "status = '[a-zéôîè]*'" app/ --include='*.py' \
    | sed "s/.*status = '//; s/'//"
  grep -roh "'status': '[a-zéôîè]*'" app/ --include='*.py' \
    | sed "s/.*'status': '//; s/'//"
) | sort -u | grep -v '^réparé$' > /tmp/status_code.txt

# Vérification : extraire les statuts du flux dans AGENTS.md
FLOW_LINE=$(grep -n '→.*→.*→' AGENTS.md | head -1 | cut -d: -f1)
if [ -n "$FLOW_LINE" ]; then
  sed -n "${FLOW_LINE}p" AGENTS.md | grep -oP '`[^`]+`' | sed 's/`//g' > /tmp/status_docs.txt
  while read s; do
    if ! grep -q "$s" /tmp/status_docs.txt; then
      echo "❌ Statut '$s' manque dans le flux de statuts AGENTS.md"
    fi
  done < /tmp/status_code.txt
fi
echo "✅ Status check done"
```

---

## 4 — Actions batch

### Vérification manuelle

- [ ] Toute nouvelle action batch définie dans `results.py:batch_action` est listée dans :
  - `AGENTS.md` (Actions batch disponibles)
  - `.opencode/skills/frontend.md`
  - `.opencode/skills/db.md`
- [ ] Les statuts résultants sont cohérents avec le code

### Commande automatique

```bash
echo "=== BATCH ACTIONS IN CODE ==="
grep -oP 'action == "\K[^"]+' app/routers/results.py | sort -u > /tmp/batch_code.txt

while read a; do
  if ! grep -q "\`$a\`" AGENTS.md; then
    echo "❌ Batch action '$a' manque dans AGENTS.md"
  fi
done < /tmp/batch_code.txt
echo "✅ Batch check done"
```

---

## 5 — results.action

### Vérification manuelle

- [ ] Toute nouvelle valeur de `action` (colonne `results.action` en base) est listée dans :
  - `AGENTS.md` (tableau Actions des résultats)
  - `docs/database.md` (tableau Actions possibles)
- [ ] Les valeurs de sync siblings (`*_sibling`) sont documentées comme telles

### Commande automatique

```bash
echo "=== ACTIONS IN CODE ==="
grep -roh "action = '[^']*'" app/ --include='*.py' \
  | sed "s/.*action = '//; s/'//" | sort -u > /tmp/actions_code.txt

while read a; do
  if grep -q "\`$a\`" AGENTS.md 2>/dev/null; then
    : ok
  elif echo "$a" | grep -q '_sibling$' && grep -q '\*_sibling' AGENTS.md; then
    : ok (wildcard pattern)
  else
    echo "❌ Action '$a' manque dans AGENTS.md"
  fi
done < /tmp/actions_code.txt
echo "✅ Actions check done"
```

---

## 6 — État du projet

### Vérification manuelle

- [ ] La section "État du projet" dans `AGENTS.md` est à jour avec les vraies fonctionnalités
- [ ] La section "Ce qui fonctionne" dans `docs/remaining-steps.md` est à jour
- [ ] Les commandes listées dans `AGENTS.md` existent dans le `Makefile`
- [ ] Le `README.md` (docs/) reflète le workflow actuel

---

## 7 — Base de données

### Vérification manuelle

- [ ] Le schéma dans `docs/database.md` et `.opencode/skills/db.md` correspond au `CREATE TABLE` dans `app/database.py`
- [ ] Les migrations (colonnes ajoutées via `ALTER TABLE`) sont documentées
- [ ] Les index sont listés

---

## 8 — Configuration

### Vérification manuelle

- [ ] Le modèle `AppConfig` dans `app/models/config.py` correspond à la structure JSON dans `docs/configuration.md`
- [ ] Les endpoints de config dans `api_config.py` sont listés dans `docs/api.md` et `AGENTS.md`

---

## 9 — Style et conventions

- [ ] Pas de `print()` ou `breakpoint()` (cf `verify.md`)
- [ ] Les imports sont triés (vérifié par `make lint`)
- [ ] Les noms de variables/fonctions en anglais
- [ ] Les messages utilisateur dans les templates en français
- [ ] Les chemins absolus depuis `app.` (pas d'import relatif)

---

## 10 — Règle ultime

Avant de déclarer une tâche terminée :

```bash
make format && make lint && make test
```

Si tout est vert, les vérifications de cohérence ci-dessus sont le dernier rempart
avant le commit.
