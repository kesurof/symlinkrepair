# Frontend — Organisation

## Principes

- Pas de build : CDN pour HTMX, Alpine.js, Tailwind
- Pages rendues côté serveur (Jinja2)
- Interactions dynamiques via HTMX (fragments HTML)
- État UI local uniquement via Alpine.js (`x-data`)
- Alpine NE stocke PAS l'état provenant du serveur (pagination, totaux, listes d'IDs)
- Les données serveur sont lues depuis le DOM via des attributs `data-*`
- Les mises à jour du DOM parent se font via `hx-swap-oob="true"` (pas d'événements custom)
- Mobile first : cartes sur mobile, tableau sur desktop
- Icônes SVG inline (pas de dépendance Font Awesome)

## Structure des templates

```
templates/
├── base.html           # Layout : nav, footer
├── index.html          # Dashboard
├── scan.html           # Page scan
├── fastscan.html       # Scan rapide
├── results.html        # Liste résultats
├── detail.html         # Détail
├── reports.html        # Rapports
├── config.html         # Configuration + explorateur dossiers
├── error.html          # Erreur générique
├── 404.html            # Page non trouvée
└── partials/
    ├── results_content.html    # Tableau résultats (swap HTMX)
    └── reports_content.html    # Tableau rapports (swap HTMX)
```

## Patterns HTMX

### Navigation avec filtres

```html
<select id="filter-status" onchange="hxNavFromFilters()">
    <option value="">Tous statuts</option>
    {% for st in statuses %}
    <option value="{{ st }}">{{ st }}</option>
    {% endfor %}
</select>
```

```javascript
async function hxNavFromFilters() {
    const params = new URLSearchParams();
    // ... lire les filtres depuis le DOM ...
    await htmx.ajax('GET', '/results?' + params.toString(), {
        target: '#results-content', pushUrl: true
    });
}
```

### Détection HTMX dans les routes

```python
is_htmx = request.headers.get("hx-request") == "true"
template = "partials/results_content.html" if is_htmx else "results.html"
```

### Mise à jour du DOM parent via OOB

Les données de pagination (total, itemIds) sont stockées dans un div caché avec `data-*` :

```html
<div id="results-data"
     data-total="{{ total }}"
     data-item-ids="[{% for item in items %}{{ item.id }}{% endfor %}]"
     style="display:none"></div>
```

Les éléments du DOM parent sont mis à jour via `hx-swap-oob="true"` :

```html
<span id="results-count" hx-swap-oob="true" class="text-sm">{{ total }} résultats</span>
```

Lecture depuis Alpine :

```javascript
currentItemIds() {
    const data = document.querySelector('#results-content #results-data');
    return data ? JSON.parse(data.dataset.itemIds) : [];
}
```

**Règle :** Ne JAMAIS utiliser Alpine `x-text`, `x-init` ou des événements custom pour synchroniser l'état serveur. Utiliser OOB + `data-*` attributes.

### Actions avec confirmation

```html
<button @click="confirmDelete = true"
        class="bg-red-100 text-red-700 px-2 py-1 rounded">
  Supprimer
</button>

<div x-show="confirmDelete" class="fixed inset-0 bg-black/40 ...">
    ...
    <button @click="batchAction('delete'); confirmDelete = false">
        Confirmer
    </button>
</div>
```

### Pagination

```html
<button hx-get="/results?page={{ page - 1 }}&{{ qp }}"
        hx-target="#results-content" hx-push-url="true">
    ←
</button>
```

Les données OOB (`#results-count`, `#results-total-num`) sont incluses dans la réponse du partial et mises à jour automatiquement.

## Patterns Alpine.js

Alpine est réservé aux micro-interactions locales :

### Sélection + batch actions

```javascript
function resultsApp() {
    return {
        selected: [],
        batchMsg: '',

        currentItemIds() {
            const data = document.querySelector('#results-content #results-data');
            return data ? JSON.parse(data.dataset.itemIds) : [];
        },

        toggleAll(checked) {
            if (checked) { this.selected = [...this.currentItemIds()]; }
            else { this.selected = []; }
        },

        async batchAction(action) {
            // POST /api/results/batch avec {action, ids: this.selected}
        }
    }
}
```

### Confirmations

```html
<div x-data="{ confirmDelete: false }">
    <button @click="confirmDelete = true">Supprimer</button>
    <div x-show="confirmDelete">...</div>
</div>
```

## Responsive

- `<table>` remplacé par des `<div class="card">` sur mobile (`hidden md:block` / `md:hidden`)
- Navigation en hamburger menu sur mobile (`x-data="{ mobileMenu: false }"`)
