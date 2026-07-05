---
name: frontend
description: Patterns HTMX, Alpine.js et Tailwind CSS
---

# frontend

## HTMX — interactions dynamiques

```html
<!-- Chargement via attributs HTML -->
<button hx-get="/scans" hx-target="#results" hx-swap="innerHTML">
  Lancer l'analyse
</button>

<!-- Échanges courants -->
hx-get="/url"          hx-target="#id"      hx-swap="innerHTML"
hx-post="/url"         hx-target="#id"      hx-swap="outerHTML"
hx-delete="/url"       hx-target="#id"      hx-swap="delete"
hx-trigger="click"     hx-indicator="#spinner"
```

## Alpine.js — état UI local

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open">Contenu masqué/affiché</div>
</div>
```

Utiliser Alpine UNIQUEMENT pour les micro-interactions : menus, modales, compteurs, validation légère.

## Tailwind CSS

- Version CDN via `<script src="https://cdn.tailwindcss.com"></script>`
- Pas de fichier CSS personnalisé
- Utiliser les classes utilitaires directement dans le HTML

## Templates Jinja2

- Extension : `.html`
- Héritage via `{% extends "base.html" %}` et `{% block %}`
- Variables : `{{ variable }}`
- Boucles : `{% for item in items %}...{% endfor %}`
- Conditions : `{% if condition %}...{% endif %}`
- Les templates reçoivent toujours `request` automatiquement (injecté par Starlette)
