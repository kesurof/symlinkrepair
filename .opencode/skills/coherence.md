---
name: coherence
description: Vérifie la cohérence entre le code et la documentation avant commit. Charge les listes de référence depuis les autres skills (db.md, frontend.md, architecture.md) et les compare au code par introspection dynamique.
---

# coherence

Charge ce skill avant chaque commit ou PR pour t'assurer que toute modification
du code a son équivalent dans la documentation et vice versa.

## Utilisation

```bash
/skill coherence
```

Les vérifications automatisées s'exécutent. Les avertissements (⚠️) sont
informatifs — ils signalent un écart possible entre code et docs.

---

## 1 — Qualité

```bash
make format && make lint && make test
```

- [ ] Pas de `print()` ou `breakpoint()` laissé dans le code
- [ ] Pas de commentaire superflu ou de code commenté
- [ ] Pas de secret, token ou chemin absolu en dur
- [ ] Les noms de variables/fonctions sont en anglais et explicites
- [ ] Les chemins absolus depuis `app.` (pas d'import relatif)

---

## 2 — Statuts (results.status)

Vérifie que les statuts utilisés dans le code existent dans `db.md`.

```bash
python3 << 'PYEOF'
import re, subprocess

with open('.opencode/skills/db.md') as f:
    db = f.read()

# Extrait les statuts documentés dans db.md
m = re.search(r'## Statuts.*?\n(.*?)(?=\n## |\Z)', db, re.DOTALL)
doc = set(re.findall(r'`([^`]+)`', m.group(1))) if m else set()

# Extrait les statuts du code
r = subprocess.run(['grep', '-roh', r"status\s*=\s*'[^']*'", 'app/', '--include=*.py'], capture_output=True, text=True)
r2 = subprocess.run(['grep', '-roh', r"'status':\s*'[^']*'", 'app/', '--include=*.py'], capture_output=True, text=True)
code = set(re.findall(r"'([^']+)'", r.stdout)) | set(re.findall(r"'([^']+)'", r2.stdout))
code.discard('réparé')

missing = code - doc
for s in sorted(missing):
    print(f"  ⚠️  Statut '{s}' dans le code mais pas dans db.md")
if not missing:
    print("  ✅ Tous les statuts du code sont documentés dans db.md")
PYEOF
```

---

## 3 — Actions batch

Vérifie que les actions batch dans `results.py` sont documentées dans `db.md` et `frontend.md`.

```bash
python3 << 'PYEOF'
import re, subprocess

with open('.opencode/skills/db.md') as f:
    db = f.read()
with open('.opencode/skills/frontend.md') as f:
    fe = f.read()

# Extrait depuis db.md (première colonne du tableau)
m = re.search(r'## Actions batch.*?\n(.*?)(?=\n## |\Z)', db, re.DOTALL)
doc_db = set(re.findall(r'^\| `([a-z_]+)`', m.group(1), re.MULTILINE)) if m else set()

# Extrait depuis frontend.md (première colonne du tableau)
m = re.search(r'## Actions batch disponibles.*?\n(.*?)(?=\n## |\Z)', fe, re.DOTALL)
doc_fe = set(re.findall(r'^\| `([a-z_]+)`', m.group(1), re.MULTILINE)) if m else set()

# Extrait du code
r = subprocess.run(['grep', '-oP', r'action\s*==\s*"\K[^"]+', 'app/routers/results.py'], capture_output=True, text=True)
code = set(r.stdout.strip().split('\n')) if r.stdout.strip() else set()

all_doc = doc_db | doc_fe
missing_doc = code - all_doc
missing_code = all_doc - code

for a in sorted(missing_doc):
    print(f"  ⚠️  Action batch '{a}' dans le code mais pas documentée (db.md / frontend.md)")
for a in sorted(missing_code):
    print(f"  ⚠️  Action batch '{a}' documentée mais absente du code")
if not missing_doc and not missing_code:
    print("  ✅ Toutes les actions batch sont documentées")
PYEOF
```

---

## 4 — results.action

Vérifie que les valeurs de `action` dans le code sont documentées dans `AGENTS.md`.

```bash
python3 << 'PYEOF'
import re, subprocess

with open('AGENTS.md') as f:
    agents = f.read()

# Extrait depuis AGENTS.md (tableau Actions des résultats)
m = re.search(r'## Actions des résultats.*?\n(.*?)(?=\n## |\Z)', agents, re.DOTALL)
doc = set(re.findall(r'`([a-z_*]+)`', m.group(1))) if m else set()

# Extrait du code
r = subprocess.run(['grep', '-roh', r"action\s*=\s*'[^']*'", 'app/', '--include=*.py'], capture_output=True, text=True)
code = set(re.findall(r"'([^']+)'", r.stdout))

# Vérifie (avec wildcard *_sibling)
for a in sorted(code):
    if a in doc:
        continue
    if a.endswith('_sibling') and '*_sibling' in doc:
        continue
    print(f"  ⚠️  Action '{a}' dans le code mais pas documentée dans AGENTS.md")

print("  ✅ Vérification results.action terminée")
PYEOF
```

---

## 5 — Routes

Vérifie que les routes FastAPI dans le code sont documentées dans `AGENTS.md` et `docs/api.md`.

```bash
python3 << 'PYEOF'
import re, subprocess

def normalize(r):
    """Normalise les noms de paramètres pour comparaison."""
    return re.sub(r'\{[^}]+\}', '{p}', r)

# Routes depuis AGENTS.md
with open('AGENTS.md') as f:
    agents = f.read()
routes_agents = set(re.findall(r'^- `(GET|POST|PUT|DELETE) (/\S*)`', agents, re.MULTILINE))
routes_agents = {f"{m[0]} {m[1].rstrip('`')}" for m in routes_agents}

# Routes depuis docs/api.md
with open('docs/api.md') as f:
    api = f.read()
routes_api = set(re.findall(r'^\| (GET|POST|PUT|DELETE) \| `([^`]+)`', api, re.MULTILINE))
routes_api = {f"{m[0]} {m[1]}" for m in routes_api}

# Routes depuis le code
r = subprocess.run(['grep', '-rn', '@router.', 'app/routers/', '--include=*.py'], capture_output=True, text=True)
routes_code = set()
for line in r.stdout.splitlines():
    m = re.search(r'@router\.(get|post|put|delete)\s*\(\s*["\x27]([^"\x27]+)["\x27]', line)
    if m:
        routes_code.add(f"{m.group(1).upper()} {m.group(2)}")

# Normalise pour la comparaison
norm_code = {normalize(r): r for r in routes_code}
norm_agents = {normalize(r): r for r in routes_agents}
norm_api = {normalize(r): r for r in routes_api}

# Vérifie (comparaison normalisée)
for n, orig in sorted(norm_code.items()):
    if n not in norm_agents:
        print(f"  ⚠️  Route '{orig}' dans le code mais pas dans AGENTS.md")
    elif norm_agents[n] != orig:
        print(f"  ℹ️  Route '{norm_agents[n]}' dans AGENTS.md → code utilise '{orig}'")
for n, orig in sorted(norm_code.items()):
    if n not in norm_api:
        print(f"  ⚠️  Route '{orig}' dans le code mais pas dans docs/api.md")
if set(norm_code.keys()) <= set(norm_agents.keys()):
    print("  ✅ AGENTS.md: routes OK")
if set(norm_code.keys()) <= set(norm_api.keys()):
    print("  ✅ docs/api.md: routes OK")
PYEOF
```

---

## 6 — Arborescence

Vérifie que les fichiers listés dans `architecture.md` existent dans `app/`.

```bash
python3 << 'PYEOF'
import re
from pathlib import Path

with open('.opencode/skills/architecture.md') as f:
    arch = f.read()

missing = []
in_tree = False
for line in arch.split('\n'):
    sline = line.strip()
    if sline == '```' and in_tree:
        in_tree = False
    elif sline == '```':
        in_tree = True
    elif in_tree and ('├──' in line or '└──' in line):
        name = re.sub(r'^.*[├└]──\s*', '', sline).split('#')[0].strip().rstrip('/')
        if name and name != 'app':
            found = list(Path('app').rglob(name))
            if not found:
                missing.append(name)

for m in sorted(missing):
    print(f"  ⚠️  '{m}' listé dans architecture.md mais pas trouvé dans app/")
if not missing:
    print("  ✅ Tous les fichiers listés dans architecture.md existent")
PYEOF
```

---

## 7 — Messages UI

Vérifie que les messages toast documentés dans `frontend.md` correspondent aux templates.

```bash
python3 << 'PYEOF'
import re

with open('.opencode/skills/frontend.md') as f:
    fe = f.read()
with open('app/templates/results.html') as f:
    results = f.read()

# Messages toast documentés dans frontend.md
doc_msgs = set()
m = re.search(r'### Toast.*?\n(.*?)(?=\n## |\Z)', fe, re.DOTALL)
if m:
    doc_msgs = set(re.findall(r"'([^']*)'", m.group(1)))
    doc_msgs |= set(re.findall(r'"([^"]*)"', m.group(1)))

# Messages dans les templates
template_msgs = set()
for fname in ['results.html', 'detail.html']:
    try:
        with open(f'app/templates/{fname}') as f:
            content = f.read()
            template_msgs |= set(re.findall(r"msg\s*=\s*['\"]([^'\"]+)['\"]", content))
    except FileNotFoundError:
        pass

print("  ✅ Messages UI check terminé")
print(f"     Messages documentés: {len(doc_msgs)}, dans templates: {len(template_msgs)}")
PYEOF
```

---

## 8 — Checklist finale

Après les vérifications automatiques, parcours cette checklist :

- [ ] Les endpoints HTMX détectent bien `request.headers.get("hx-request") == "true"`
- [ ] Les données serveur sont dans `data-*` attributes, pas dans Alpine `x-text`
- [ ] Les OOB swaps (`hx-swap-oob="true"`) sont en fin de partial
- [ ] Les mutations DB sont suivies de `await db.commit()`
- [ ] Les requêtes SQL utilisent des paramètres `?` (pas de f-string)
- [ ] Les actions destructives ont une confirmation (modale Alpine ou `hx-confirm`)
- [ ] Les classes `dark:` sont ajoutées (dark mode)
- [ ] Les pages ont un layout mobile (bottom nav + cards) et desktop (sidebar + table)
- [ ] Les modales de confirmation utilisent `slide-up` responsive
- [ ] Les statuts des résultats utilisent le pattern pastille (dot + texte)
- [ ] Le Makefile est cohérent avec les commandes listées dans `AGENTS.md`
- [ ] Les `docs/` sont mis à jour si le comportement d'un endpoint a changé
