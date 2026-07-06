# Frontend — Organisation

## Principes

- Pas de build : CDN pour HTMX, Alpine.js, Tailwind
- Pages rendues côté serveur (Jinja2)
- Interactions dynamiques via HTMX (fragments HTML)
- État UI local uniquement via Alpine.js (`x-data`)
- Alpine NE stocke PAS l'état provenant du serveur (pagination, totaux, listes d'IDs)
- Les données serveur sont lues depuis le DOM via des attributs `data-*`
- Les mises à jour du DOM parent se font via `hx-swap-oob="true"` (pas d'événements custom)
- **Mobile first** : cartes sur mobile, tableau sur desktop ; bottom nav sur mobile, sidebar desktop
- **Dark mode** : classe `dark` sur `<html>`, persisté en localStorage, system preference au premier lancement
- **Icônes SVG inline** (Heroicons, pas de dépendance externe)
- **Font** : Inter (Google Fonts CDN)
- **Couleurs** : palette `brand` indigo, configurée dans `tailwind.config`

## Structure des templates

```
templates/
├── base.html           # Layout : sidebar desktop + bottom nav mobile
├── index.html          # Dashboard
├── scan.html           # Page scan (complet + rapide fusionnés)
├── results.html        # Liste résultats
├── detail.html         # Détail
├── reports.html        # Rapports d'exécution
├── config.html         # Configuration + explorateur dossiers
├── error.html          # Erreur générique (étend base.html)
├── 404.html            # Page non trouvée (étend base.html)
└── partials/
    ├── results_content.html    # Tableau/cards résultats (swap HTMX)
    └── reports_content.html    # Tableau/cards rapports (swap HTMX)

static/
├── htmx.min.js         # HTMX 2.x
├── alpine.min.js       # Alpine.js 3.x
├── app.css             # Styles custom (animations, skeleton)
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

- **Mobile-first** : toute page commence par le layout mobile (bottom nav), s'adapte au desktop (sidebar)
- `<table>` remplacé par des `<div class="card">` sur mobile (`hidden md:block` / `md:hidden`)
- **Bottom nav** : 5 onglets fixes en bas sur mobile (`< 768px`), `pb-16` sur le main
- **Sidebar** : cachée sur mobile, visible sur desktop ; rétractable (`w-56` / `w-16`)
- **Safe area** : `pb-[env(safe-area-inset-bottom)]` pour les appareils avec notch
- **Dark mode** : classe `dark` sur `<html>`, persisté dans `localStorage`
