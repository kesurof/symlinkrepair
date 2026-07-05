# Frontend — Organisation

## Principes

- Pas de build : CDN pour HTMX, Alpine.js, Tailwind
- Pages rendues côté serveur (Jinja2)
- Interactions dynamiques via HTMX (fragments HTML)
- État UI local via Alpine.js (`x-data`)
- Mobile first : cartes sur mobile, tableau sur desktop
- Icônes SVG inline (pas de dépendance Font Awesome)

## Structure des templates

```
templates/
├── base.html           # Layout : header, footer, nav
├── index.html          # Dashboard
├── scan.html           # Page scan
├── results.html        # Liste éléments
├── detail.html         # Détail
├── reports.html        # Rapports
├── config.html         # Configuration + explorateur dossiers
└── partials/
    ├── scan_status.html
    ├── result_card.html
    ├── result_table.html
    ├── folder_browser.html
    └── stats_widget.html
```

## Patterns HTMX

### Navigation

```html
<nav>
  <a href="/" hx-get="/" hx-target="#content" hx-push-url="true">Dashboard</a>
  <a href="/scan" hx-get="/scan" hx-target="#content" hx-push-url="true">Scan</a>
</nav>
<main id="content">
  {% block content %}{% endblock %}
</main>
```

### Actions avec confirmation

```html
<button hx-post="/results/42/process"
        hx-target="#result-42"
        hx-confirm="Confirmer le nettoyage réel de cet élément ?"
        class="bg-red-500 text-white px-3 py-1 rounded">
  Nettoyer
</button>
```

### Polling pour scan long

```html
<div hx-get="/scan/status/{{ scan_id }}"
     hx-trigger="every 2s"
     hx-target="#scan-progress"
     hx-swap="innerHTML">
</div>
```

## Patterns Alpine.js

### Explorateur de dossiers

```html
<div x-data="folderBrowser()">
  <template x-for="dir in directories">
    <div @click="navigate(dir.path)">...</div>
  </template>
</div>
```

### Filtres rapides

```html
<div x-data="{ search: '', source: 'all' }">
  <input x-model="search" placeholder="Rechercher...">
  <select x-model="source">
    <option value="all">Tous</option>
    <option value="radarr">Radarr</option>
    <option value="sonarr">Sonarr</option>
  </select>
  <!-- HTMX prend le relais pour la soumission -->
  <button hx-get="/results"
          hx-vals='{"q": search, "source": source}'
          hx-target="#results">
    Filtrer
  </button>
</div>
```

### Confirmation en 2 étapes pour actions destructives

```html
<div x-data="{ step: 'initial' }">
  <template x-if="step === 'initial'">
    <button @click="step = 'confirm'" class="bg-orange-500 text-white px-3 py-1 rounded">
      Nettoyage réel
    </button>
  </template>
  <template x-if="step === 'confirm'">
    <div class="flex gap-2">
      <span class="text-sm text-red-600">Confirmer ?</span>
      <button @click="step = 'initial'" class="bg-gray-300 px-2 py-1 rounded text-sm">Annuler</button>
      <button hx-post="/scan/radarr?mode=clean"
              hx-target="#scan-results"
              class="bg-red-600 text-white px-2 py-1 rounded text-sm">
        Confirmer
      </button>
    </div>
  </template>
</div>
```

## Responsive

- `<table>` remplacé par des `<div class="card">` sur mobile
- Classe `hidden md:table-cell` pour colonnes masquées
- Navigation en hamburger menu sur mobile (`x-data="{ menuOpen: false }"`)
