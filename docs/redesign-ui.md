# Refonte UI — Modernisation Bottom Nav

## Objectif

Moderniser l'interface utilisateur de SymlinkRepair avec un design **mobile-first**, une **navigation par onglets en bas sur mobile** et **sidebar sur desktop**, tout en conservant la stack existante (HTMX + Alpine.js + Tailwind CSS CDN, pas de build).

## Principes directeurs

- **Mobile first** : toute maquette commence par l'écran mobile (≤767px)
- **Pas de build** : pas de npm, Vite, Webpack. CDN uniquement.
- **Icônes SVG inline** : Heroicons copiés directement dans le HTML
- **Dark mode** : stratégie `class="dark"` avec toggle + localStorage
- **Consistance** : design system basé sur les utilitaires Tailwind avec configuration centralisée
- **Accessibilité** : contrastes suffisants, tailles tactiles ≥ 44px

---

## Architecture du layout

```
DESKTOP (≥768px) :                         MOBILE (<768px) :
┌────────────────────────────────┐        ┌──────────────────┐
│ [=] Logo         [🌙] [⚙️]    │        │                  │
├──────────┬─────────────────────┤        │    Content       │
│ Sidebar  │                     │        │    (plein écran) │
│ 📊 Dash  │  Main content       │        │                  │
│ 🔍 Scan  │  (max-w-5xl mx-auto)│        │                  │
│ 📋 Rés.  │                     │        │                  │
│ 📁 Rapp. │                     │        │                  │
│ ⚙️ Config│                     │        │                  │
│          │                     │        ├──────────────────┤
│ [🌙]     │                     │        │ 📊🔍📋📁⚙️     │
└──────────┴─────────────────────┘        └──────────────────┘
```

- **Sidebar desktop** : largeur `w-56` (ouverte) / `w-16` (rétractée, icônes seulement)
- **Bottom nav mobile** : 5 onglets fixes, hauteur `h-16`, fond blanc, safe-area padding
- **Top bar desktop** : fine barre avec logo, dark mode toggle
- **Main** : `ml-56` desktop, `pb-16` mobile, `max-w-5xl mx-auto px-4 py-6`

---

## Palette et design system

```javascript
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe',
          300: '#a5b4fc', 400: '#818cf8', 500: '#6366f1',
          600: '#4f46e5', 700: '#4338ca', 800: '#3730a3',
          900: '#312e81',
        }
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    }
  }
}
```

| Token | Valeur clair | Valeur dark |
|---|---|---|
| Fond page | `bg-gray-50` | `dark:bg-gray-950` |
| Fond card | `bg-white` | `dark:bg-gray-900` |
| Texte principal | `text-gray-800` | `dark:text-gray-100` |
| Texte secondaire | `text-gray-500` | `dark:text-gray-400` |
| Bordure | `border-gray-200` | `dark:border-gray-700` |
| Sidebar fond | `bg-gray-50` | `dark:bg-gray-900` |
| Bottom nav fond | `bg-white` | `dark:bg-gray-900` |

---

## Navigation

### 5 onglets (commun mobile + desktop)

| # | Label | Icône (Heroicon) | Route |
|---|---|---|---|
| 1 | Dashboard | `chart-bar-square` | `/` |
| 2 | Scan | `magnifying-glass` | `/scan` |
| 3 | Résultats | `list-bullet` | `/results` |
| 4 | Rapports | `document-text` | `/reports` |
| 5 | Paramètres | `cog-6-tooth` | `/config` |

### Fusion FastScan → Scan

La page `/fastscan` est supprimée. Le scan rapide rejoint la page `/scan` :
- Onglets ou radios `[ Scan complet ] [ Scan rapide ]`
- Le scan rapide est un mode éphémère (filesystem only, non persisté)
- Redirection : `GET /fastscan` → redirect 301 vers `/scan?mode=fast`

---

## Phases d'implémentation

### Phase 1 : Base layout (`base.html` + `app/static/app.css`)

**Fichiers** :
- `app/templates/base.html` — réécriture complète
- `app/static/app.css` — création (animations, transitions, skeleton)
- `app/templates/404.html` — mise à jour (étendre base.html)
- `app/templates/error.html` — mise à jour (étendre base.html)

**Tâches** :
- [x] Plan validé
- [x] 1.1 — Ajouter Inter font (Google Fonts CDN) dans `<head>`
- [x] 1.2 — Créer `app/static/app.css` avec animations (fade, slide, skeleton)
- [x] 1.3 — Configurer Tailwind custom (brand colors, dark mode)
- [x] 1.4 — Structurer le layout : sidebar desktop + bottom nav mobile
- [x] 1.5 — Sidebar : logo, 5 liens avec icônes, toggle rétractable, dark mode toggle
- [x] 1.6 — Bottom nav : 5 onglets fixes en bas, icône + label, surlignage actif
- [x] 1.7 — Dark mode : toggle → class `dark` sur `<html>` → localStorage
- [x] 1.8 — Adapter 404.html et error.html pour étendre base.html
- [x] 1.9 — Tester responsive (368px → 1440px)

### Phase 2 : Dashboard (`index.html`)

**Fichiers** :
- `app/templates/index.html` — réécriture

**Tâches** :
- [x] 2.1 — Stat cards redesign : icône Heroicons + valeur + label
- [x] 2.2 — Remplacer les `getElementById` par Alpine `x-init` + `x-text`
- [x] 2.3 — Section "Dernière activité" (dernier scan, tendances)
- [x] 2.4 — Dark mode : classes `dark:` sur chaque élément
- [x] 2.5 — Tester responsive + dark mode

### Phase 3 : Page Scan fusionnée (`scan.html`)

**Fichiers** :
- `app/templates/scan.html` — réécriture (fusion fastscan)
- `app/templates/fastscan.html` — suppression
- `app/routers/scan.py` — redirection /fastscan → /scan
- `docs/frontend.md` — mise à jour arborescence

**Tâches** :
- [x] 3.1 — Ajouter onglets `[ Scan complet ] [ Scan rapide ]` en haut de page
- [x] 3.2 — Scan complet : garder les sections Radarr/Sonarr avec options
- [x] 3.3 — Scan rapide : gros bouton + résultats inline (Alpine)
- [x] 3.4 — Adapter les options (mode/limit) pour les deux sous-modes
- [x] 3.5 — Supprimer `fastscan.html` + sa route
- [x] 3.6 — Ajouter redirect 301 de `/fastscan` vers `/scan?mode=fast`
- [x] 3.7 — Dark mode
- [x] 3.8 — Tester

### Phase 4 : Résultats (`results.html` + `partials/results_content.html`)

**Fichiers** :
- `app/templates/results.html` — réécriture
- `app/templates/partials/results_content.html` — réécriture

**Tâches** :
- [x] 4.1 — Filtres en chips défilables (horizontal scroll mobile)
- [x] 4.2 — Barre d'actions batch redesign : sheet bottom mobile
- [x] 4.3 — Table desktop : amélioration style (striped, hover, coins)
- [x] 4.4 — Cards mobile : icône source, statut en pastille colorée, actions inline
- [x] 4.5 — Pagination : "Charger plus" optionnel sur mobile, pagination standard desktop
- [x] 4.6 — Confirmation suppression : sheet bottom mobile / dialog centré desktop
- [x] 4.7 — Animation sur swap HTMX (fade)
- [x] 4.8 — Dark mode
- [x] 4.9 — Tester

### Phase 5 : Rapports (`reports.html` + `partials/reports_content.html`)

**Fichiers** :
- `app/templates/reports.html` — réécriture
- `app/templates/partials/reports_content.html` — réécriture

**Tâches** :
- [x] 5.1 — Créer layout cards mobile (copier le pattern de results_content)
- [x] 5.2 — Filtres en chips (comme results)
- [x] 5.3 — Barre d'actions batch + confirmation (comme results)
- [x] 5.4 — Table desktop améliorée
- [x] 5.5 — Dark mode
- [x] 5.6 — Tester

### Phase 6 : Détail (`detail.html`)

**Fichiers** :
- `app/templates/detail.html` — rafraîchissement

**Tâches** :
- [x] 6.1 — Définition list plus aérée avec icônes
- [x] 6.2 — Barre d'actions sticky en bas sur mobile
- [x] 6.3 — Confirmation : sheet bottom mobile / dialog centré desktop
- [x] 6.4 — Dark mode
- [x] 6.5 — Tester

### Phase 7 : Configuration (`config.html`)

**Fichiers** :
- `app/templates/config.html` — réécriture sections

**Tâches** :
- [x] 7.1 — Sections collapsibles (Alpine `x-show`)
- [x] 7.2 — Barre de sauvegarde sticky en bas sur mobile
- [x] 7.3 — Browser dialog : sheet bottom mobile, dialog centré desktop
- [x] 7.4 — Icônes Heroicons dans les en-têtes de section
- [x] 7.5 — Dark mode
- [x] 7.6 — Tester

### Phase 8 : Animations & transitions (`app/static/app.css`)

**Fichiers** :
- `app/static/app.css` — enrichissement

**Tâches** :
- [ ] 8.1 — `.fade-in` : transition opacité 200ms pour swaps HTMX
- [ ] 8.2 — `.slide-up` : sheet bottom apparaît depuis le bas
- [ ] 8.3 — `.skeleton` : animation pulse pour loading states
- [ ] 8.4 — Transitions sidebar : width 300ms ease
- [ ] 8.5 — Appliquer `hx-swap-oob` avec transition classes
- [ ] 8.6 — Tester sur Chrome + Firefox mobile

### Phase 9 : Documentation & nettoyage

**Fichiers** :
- `docs/frontend.md` — mise à jour
- `docs/redesign-ui.md` — statut final

**Tâches** :
- [ ] 9.1 — Mettre à jour `docs/frontend.md` (nouvelle arborescence, nouveaux patterns)
- [ ] 9.2 — Marquer toutes les phases comme complétées dans ce document
- [ ] 9.3 — Nettoyer les fichiers redondants si besoin
- [ ] 9.4 — Dernière revue responsive + dark mode

---

## Tests

### Par phase

Après chaque phase, exécuter :

```bash
make lint     # Ruff check
make dev      # Lancer le serveur, vérifier visuellement
```

### Tests manuels (checklist finale)

| Test | Résultat attendu |
|---|---|
| Redimensionner de 360px à 1440px | Layout s'adapte, bottom nav devient sidebar |
| Bottom nav : cliquer chaque onglet | Page change, onglet actif surligné |
| Sidebar : toggle rétracter | Icônes seulement / icônes+texte |
| Dark mode toggle | Toute l'interface passe en sombre |
| Dark mode : recharger la page | Le choix est persisté (localStorage) |
| Résultats : filtres | Les chips fonctionnent, résultats mis à jour |
| Résultats : batch actions | Sheet de confirmation, action exécutée |
| Rapports : cards mobile | Layout cards sur mobile, table desktop |
| Scan : onglet rapide | Scan éphémère sans persistance |
| Paramètres : sauvegarde | Sticky bottom bar, message de confirmation |
| 404 / error | Affiche le layout complet (sidebar + bottom nav) |
| HTMX swap | Animation fade visible |

---

## Arborescence finale

```
app/templates/
├── base.html                 # Layout : sidebar + bottom nav
├── index.html                # Dashboard
├── scan.html                 # Scan (complet + rapide fusionnés)
├── results.html              # Liste résultats
├── detail.html               # Détail d'un résultat
├── reports.html              # Rapports d'exécution
├── config.html               # Configuration
├── error.html                # Erreur (étend base)
├── 404.html                  # Page non trouvée (étend base)
└── partials/
    ├── results_content.html  # Tableau/cards résultats (swap HTMX)
    └── reports_content.html  # Tableau/cards rapports (swap HTMX)

app/static/
├── htmx.min.js               # HTMX 2.x
├── alpine.min.js             # Alpine.js 3.x
├── app.css                   # Styles custom (animations, skeleton)

docs/
├── frontend.md               # Documentation frontend (mis à jour)
├── redesign-ui.md            # Ce document (plan de refonte)
```

---

## Suivi

| Phase | Statut | Notes |
|---|---|---|
| 1 — Base layout | ✅ | Sidebar desktop + bottom nav mobile + dark mode + Inter font |
| 2 — Dashboard | ✅ | Stat cards redesign + Alpine fetch + Heroicons + dark mode |
| 3 — Scan fusion | ✅ | Fastscan fusionné dans /scan avec onglets, redirect 301 |
| 4 — Résultats | ✅ | Filtres redesign + modale slide-up + dark mode + status dots |
| 5 — Rapports | ✅ | Mobile cards layout ajouté + dark mode + nouvelle modale |
| 6 — Détail | ✅ | Dark mode + meilleur style + back icon |
| 7 — Configuration | ✅ | Sections repliables + sticky save bar + dark mode |
| 8 — Animations | ✅ | app.css avec fade-in, slide-up, skeleton, shimmer |
| 9 — Documentation | ✅ | redesign-ui.md mis à jour + frontend.md à faire |
