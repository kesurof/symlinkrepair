# Configuration dynamique

## Problème

Toutes les valeurs suivantes sont différentes pour chaque utilisateur :

- URLs et clés API des serveurs Radarr / Sonarr
- Noms des conteneurs Docker
- Chemins des bibliothèques média (library roots)
- Préfixes de chemins surveillés (target prefixes)
- Webhook et préférences Discord
- Limites et comportements par défaut

Les scripts existants stockent ces valeurs dans des fichiers JSON statiques
qu'il faut éditer à la main ou via un assistant interactif en terminal.
L'application doit permettre de **tout configurer depuis l'interface**,
sans jamais éditer de fichier manuellement.

## Approche : 3 types de champs

| Type | Exemples | UI |
|------|----------|----|
| **Chemins répertoires** | `LIBRARY_ROOTS`, `TARGET_PREFIXES` | Explorateur de dossiers (navigation) |
| **Valeurs scalaires** | URL, clé API, conteneur, webhook | Champ texte, masquage pour secrets |
| **Booléens** | notifications, refresh, search, keep_symlinks | Toggle / interrupteur |

> **Note :** `TARGET_PREFIXES` sont des points de montage réels (rclone,
> mergerfs, unionfs ou équivalent). Ce sont donc des répertoires existants
> sur le système, accessibles via l'explorateur de dossiers au même titre
> que `LIBRARY_ROOTS`.

---

## 1. Explorateur de dossiers (pour `LIBRARY_ROOTS`)

### Backend — `GET /api/browse?path=/mnt`

```json
{
  "current": "/mnt",
  "parent": "/",
  "directories": [
    {"name": "userdata", "path": "/mnt/userdata", "is_symlink": false},
    {"name": "media",    "path": "/mnt/media",    "is_symlink": true}
  ],
  "can_go_up": true
}
```

**Sécurité :**
- `Path(path).resolve()` — pas de `..` ni de symlink malveillant
- Vérification que le chemin résolu commence par l'un des `browse_roots`
- Ne liste que les dossiers (pas les fichiers)
- `browse_roots` défini dans `data/config.json` (ex: `["/mnt", "/data"]`)
- Ne remonte jamais au-delà de `/`

### Frontend — composant Alpine.js réutilisable

```html
<div x-data="folderBrowser('/mnt')">
  <div class="flex items-center gap-2 mb-2">
    <span class="text-sm font-mono text-gray-600" x-text="currentPath"></span>
  </div>
  <div class="border rounded overflow-hidden">
    <template x-for="dir in directories">
      <div class="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer border-b last:border-b-0"
           @click="navigate(dir.path)">

        <svg class="w-4 h-4 text-amber-500 mr-2 shrink-0">📁</svg>
        <span x-text="dir.name" class="text-sm truncate"></span>

        <button class="ml-auto text-xs text-blue-600 hover:underline whitespace-nowrap"
                @click.stop="$dispatch('select-folder', { field: fieldName, path: dir.path })">
          Sélectionner
        </button>
      </div>
    </template>
  </div>
  <button x-show="canGoUp" @click="goUp()" class="text-sm mt-1 text-gray-500 hover:text-gray-700">
    ↑ Dossier parent
  </button>
</div>
```

**Fonctionnalités :**
- `x-init` : charge le dossier initial via `fetch /api/browse`
- `navigate(path)` : recharge l'explorateur avec le nouveau chemin
- `goUp()` : remonte au parent (avec `path.parent`)
- `$dispatch('select-folder', {field, path})` : notifie le champ parent

### Intégration dans la page

Chaque champ de type **chemin répertoire** est accompagné d'un bouton "Parcourir"
qui ouvre l'explorateur dans une modale HTMX / Alpine.js :

```html
<div x-data="{ path: '/mnt/userdata/radarr/movies' }">
  <label>Racine bibliothèque Radarr</label>
  <div class="flex gap-2">
    <input type="text" x-model="path" class="flex-1 border rounded px-2 py-1 font-mono text-sm">
    <button @click="$refs.browserModal.showModal()"
            class="bg-gray-100 border rounded px-3 py-1 text-sm hover:bg-gray-200">
      Parcourir
    </button>
    <button @click="addPath()" class="bg-blue-500 text-white rounded px-3 py-1 text-sm">
      +
    </button>
  </div>
</div>
```

---

## 2. Préfixes surveillés (pour `TARGET_PREFIXES`)

Les préfixes comme `/mnt/decypharr/alldebrid/` sont des **points de montage
réels** (rclone mount, mergerfs, unionfs, ou équivalent). Ce sont donc des
répertoires existants sur le système : l'explorateur de dossiers est parfaitement
adapté, **exactement comme pour LIBRARY_ROOTS**.

### UI : même explorateur que LIBRARY_ROOTS

Le composant `folderBrowser` est réutilisé à l'identique :

```html
<div x-data="{ prefixes: ['/mnt/decypharr/alldebrid/'] }">
  <label>Points de montage surveillés (AllDebrid / Decypharr)</label>
  <p class="text-xs text-gray-500 mb-2">
    Répertoires où sont montés les volumes rclone / mergerfs contenant
    les fichiers débridés.
  </p>

  <div class="space-y-1 mb-2">
    <template x-for="(p, i) in prefixes" :key="i">
      <div class="flex items-center gap-2 bg-gray-50 rounded px-3 py-1.5 text-sm font-mono">
        <span class="flex-1" x-text="p"></span>
        <button @click="prefixes.splice(i, 1)" class="text-red-400 hover:text-red-600 text-xs">✕</button>
      </div>
    </template>
  </div>

  <button @click="$refs.browserModal.showModal()"
          class="text-blue-600 text-sm hover:underline">
    + Ajouter un point de montage
  </button>

  <!-- Modale explorateur (même composant que pour LIBRARY_ROOTS) -->
  <dialog x-ref="browserModal" class="rounded-lg shadow-xl border p-4 w-full max-w-lg">
    <div x-data="folderBrowser('/mnt')">
      ...
    </div>
  </dialog>
</div>
```

---

## 3. Valeurs scalaires (URL, clés, conteneur, webhook)

### UI standard

```html
<div>
  <label class="block text-sm font-medium text-gray-700">URL Radarr</label>
  <input type="url" x-model="config.radarr.url"
         placeholder="http://radarr:7878"
         class="w-full border rounded px-2 py-1.5 text-sm">
</div>

<div>
  <label class="block text-sm font-medium text-gray-700">Clé API Radarr</label>
  <div class="flex gap-2">
    <input :type="showKey ? 'text' : 'password'"
           x-model="config.radarr.api_key"
           class="flex-1 border rounded px-2 py-1.5 text-sm font-mono">
    <button @click="showKey = !showKey" class="text-xs text-gray-500 hover:text-gray-700">
      <span x-text="showKey ? 'Masquer' : 'Afficher'"></span>
    </button>
  </div>
</div>
```

**Règles pour les secrets :**
- Les champs API KEY et WEBHOOK sont en `type="password"` par défaut
- Bouton "Afficher / Masquer" pour révélation temporaire
- Jamais envoyés en GET, uniquement en POST (corps JSON)
- Masqués dans les logs backend (`****`)
- Enregistrés dans `data/config.json` (ignoré par git)

---

## 4. Booléens et options par défaut

```html
<div class="space-y-3">
  <label class="flex items-center gap-3">
    <input type="checkbox" x-model="config.defaults.rescan" class="rounded">
    <span class="text-sm">Refresh Radarr / Sonarr après traitement</span>
  </label>

  <label class="flex items-center gap-3">
    <input type="checkbox" x-model="config.defaults.search" class="rounded">
    <span class="text-sm">Recherche automatique après nettoyage</span>
  </label>

  <label class="flex items-center gap-3">
    <input type="checkbox" x-model="config.defaults.keep_symlinks" class="rounded">
    <span class="text-sm">Conserver les symlinks locaux après suppression</span>
  </label>

  <div>
    <label class="block text-sm font-medium text-gray-700">Limite par défaut</label>
    <input type="number" x-model="config.defaults.limit" min="1" max="500"
           class="w-24 border rounded px-2 py-1.5 text-sm">
  </div>
</div>
```

---

## Vue d'ensemble de la page de configuration

```
┌─────────────────────────────────────────────────┐
│  ⚙️ Paramètres                                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ── Radarr ──────────────────────────────────   │
│  URL              [http://radarr:7878         ] │
│  Clé API          [••••••••••••] Afficher     │
│  Conteneur        [radarr                     ] │
│  Bibliothèques    [/mnt/...] [+] [Parcourir]   │
│                   [/mnt/...] ✕                  │
│  Préfixes ALD     [/mnt/decypharr/...] [+]     │
│                   [/mnt/uniondebr/...] ✕        │
│  [Tester la connexion]                          │
│                                                 │
│  ── Sonarr ──────────────────────────────────   │
│  ... (même structure que Radarr)                │
│                                                 │
│  ── Discord ────────────────────────────────   │
│  Actif              [✔]                         │
│  Webhook            [https://discord.com/...  ] │
│                                                 │
│  ── Valeurs par défaut ─────────────────────   │
│  Refresh auto       [✔]                         │
│  Recherche auto     [✔]                         │
│  Garder symlinks    [ ]                         │
│  Limite fichiers    [50]                        │
│                                                 │
  │  ── Explorateur ── (modale, même composant ──   │
  │  │    pour LIBRARY_ROOTS et TARGET_PREFIXES)     │
  │  📁 /mnt                                       │
  │  ├── 📁 userdata/         [Sélectionner]        │
  │  ├── 📁 media/            [Sélectionner]        │
  │  └── 📁 downloads/        [Sélectionner]        │
  │  [↑ Dossier parent]                             │
  │                                                 │
  │  [💾 Enregistrer]                               │
└─────────────────────────────────────────────────┘
```

---

## Stockage : `data/config.json`

```json
{
  "radarr": {
    "url": "http://radarr:7878",
    "api_key": "",
    "container": "radarr",
    "library_roots": ["/mnt/userdata/radarr/movies"],
    "target_prefixes": ["/mnt/decypharr/alldebrid/"]
  },
  "sonarr": {
    "url": "http://sonarr:8989",
    "api_key": "",
    "container": "sonarr",
    "library_roots": ["/mnt/userdata/sonarr/series"],
    "target_prefixes": ["/mnt/decypharr/alldebrid/"]
  },
  "discord": {
    "enabled": false,
    "webhook": ""
  },
  "defaults": {
    "limit": 50,
    "rescan": true,
    "search": true,
    "keep_symlinks": false
  },
  "browse_roots": ["/mnt", "/data"]
}
```

- Fichier ignoré par git (dans `data/`)
- Rechargé au démarrage et après chaque sauvegarde
- Sauvegarde via `POST /api/config` avec le JSON complet

## API

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/api/config` | Lire la config (secrets masqués) |
| `POST` | `/api/config` | Sauvegarder la config |
| `GET` | `/api/browse?path=...` | Explorer les dossiers |
| `POST` | `/api/config/test-radarr` | Tester connexion Radarr |
| `POST` | `/api/config/test-sonarr` | Tester connexion Sonarr |

## Sécurité

- Les clés API et webhooks ne sont jamais renvoyés en clair par `GET /api/config`
- L'explorateur est limité aux `browse_roots` configurés
- Toute modification est persistée immédiatement dans `data/config.json`
- Les scripts sont invoqués avec la configuration courante à chaque exécution
