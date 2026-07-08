---
name: frontend
description: Patterns HTMX, Alpine.js et Tailwind CSS
---

# frontend

## HTMX + Alpine — Règles strictes

### Mise à jour du DOM après un swap HTMX
- **NE PAS** utiliser Alpine `x-text`, `x-init`, ou des événements custom pour mettre à jour des éléments en dehors de la zone swap
- **NE PAS** utiliser `htmx:afterSwap`, des callbacks JS, ou des événements dispatcher pour synchroniser Alpine
- **TOUJOURS** utiliser `hx-swap-oob="true"` dans le partial HTMX pour mettre à jour les éléments du DOM parent
- Les données de pagination (`total`, `itemIds`, `page`) sont stockées dans des attributs `data-*` sur un div caché dans le partial, pas dans Alpine
- Alpine est utilisé UNIQUEMENT pour l'interactivité locale (sélection, batch actions, menus, modales), pas pour l'état global de la page

### Pattern OOB (out-of-band)
1. Dans le template parent : éléments statiques avec `id`, pas de binding Alpine
2. Dans le partial : mêmes `id` avec `hx-swap-oob="true"` en fin de partial
3. HTMX extrait les éléments OOB et les swap dans le parent automatiquement

### Exemple
```html
{# Parent : élément statique avec id #}
<span id="results-count" class="text-sm">{{ total }} résultats</span>

{# Partial : OOB qui remplace l'élément parent #}
<span id="results-count" hx-swap-oob="true" class="text-sm">{{ total }} résultats</span>
```

### Détection HTMX dans les routes
```python
is_htmx = request.headers.get("hx-request") == "true"
template = "partials/results_content.html" if is_htmx else "results.html"
```

### Données du contexte accessibles depuis JS
Stocker les métadonnées dans un div caché avec `data-*` :
```html
<div id="results-data"
     data-total="{{ total }}"
     data-item-ids="[{% for item in items %}{{ item.id }}{% if not loop.last %},{% endif %}{% endfor %}]"
     style="display:none"></div>
```

Lecture depuis Alpine ou JS :
```javascript
const data = document.getElementById('results-data');
const total = parseInt(data.dataset.total);
const ids = JSON.parse(data.dataset.itemIds);
```

## HTMX — interactions dynamiques

```html
<!-- Navigation avec filtres -->
<select onchange="hxNavFromFilters()">
    <option value="">Tous statuts</option>
    {% for st in statuses %}
    <option value="{{ st }}">{{ st }}</option>
    {% endfor %}
</select>

<script>
async function hxNavFromFilters() {
    const params = new URLSearchParams();
    const st = document.getElementById('filter-status').value;
    if (st) params.set('status', st);
    await htmx.ajax('GET', '/results?' + params.toString(), {
        target: '#results-content', pushUrl: true
    });
}
</script>
```

## Alpine.js — état UI local

```javascript
function resultsApp() {
    return {
        selected: [],
        batchMsg: '',
        confirmDelete: false,

        currentItemIds() {
            const data = document.querySelector('#results-content #results-data');
            return data ? JSON.parse(data.dataset.itemIds) : [];
        },

        toggleAll(checked) {
            this.selected = checked ? [...this.currentItemIds()] : [];
        },

        async batchAction(action) {
            const resp = await fetch('/api/results/batch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action, ids: this.selected})
            });
            if ((await resp.json()).ok) {
                this.selected = [];
                hxNavFromFilters();
            }
        }
    }
}
```

## Actions batch disponibles

| action | Bouton | Effet |
|--------|--------|-------|
| `process` | Traiter | DELETE API Radarr/Sonarr + recherche |
| `process_season` | Traiter la saison | DELETE API Sonarr + marquage `recherche` si sans `file_id` + recherche saison complète. Retourne `search_triggered` |
| `verify_season` | Vérifier la saison | Vérifie les symlinks sur le filesystem |
| `fix` | Marquer remplacé | Flag manuel |
| `ignore` | Ignorer | Cache le résultat |
| `recheck` | Revérifier | Remet en file d'attente |
| `delete` | Supprimer | Supprime la ligne (avec confirmation) |

### Toast « Traiter la saison »

```javascript
// Dans groupSeasonAction() — quand search_triggered est true
if (data.search_triggered) {
    const parts = [];
    if (data.affected > 0) parts.push(data.affected + ' supprimé(s)');
    parts.push('recherche déclenchée');
    msg = parts.join(', ');
}
// Affiche : "3 supprimé(s), recherche déclenchée" ou "recherche déclenchée"
```

## Tailwind CSS

- Version CDN via `<script src="https://cdn.tailwindcss.com"></script>`
- Configuration custom dans un `<script>` après le CDN :
  - Dark mode : `darkMode: 'class'`
  - Couleurs brand indigo : `brand-50` à `brand-900`
  - Font : `Inter, system-ui, sans-serif`
- Fichier CSS custom : `app/static/app.css` (animations fade-in, slide-up, skeleton)
- Dark mode : classe `dark` sur `<html>`, persisté localStorage, system preference au 1er lancement

## Templates Jinja2

- Extension : `.html`
- Héritage via `{% extends "base.html" %}` et `{% block %}`
- Variables : `{{ variable }}`
- Boucles : `{% for item in items %}...{% endfor %}`
- Conditions : `{% if condition %}...{% endif %}`
- Les templates reçoivent toujours `request` automatiquement (injecté par Starlette)
- Les modales de confirmation utilisent le pattern `slide-up` (sheet bottom mobile / dialog desktop)
- Les statuts des résultats utilisent des pastilles colorées (dot + texte) dans des `rounded-full`
