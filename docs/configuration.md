# Configuration dynamique

## Problème

Les chemins de bibliothèques (`RADARR_LIBRARY_ROOTS`, `SONARR_LIBRARY_ROOTS`)
sont différents pour chaque utilisateur. Les scripts existants utilisent des
fichiers JSON statiques. L'application doit permettre de les configurer depuis
l'interface, sans éditer de fichiers.

## Solution : module d'exploration de dossiers

### Backend — `GET /api/browse`

```
GET /api/browse?path=/mnt
```

Réponse :

```json
{
  "current": "/mnt",
  "parent": "/",
  "directories": [
    {"name": "userdata", "path": "/mnt/userdata", "is_symlink": false},
    {"name": "media", "path": "/mnt/media", "is_symlink": true}
  ],
  "can_go_up": true
}
```

### Backend — validation

- Résolution sécurisée : `Path(path).resolve()`
- Vérification que le chemin résolu est dans les préfixes autorisés
- Liste uniquement les dossiers (pas les fichiers)
- Le parent `..` n'est pas listé si déjà à la racine autorisée
- Ne pas exposer `/`, `/etc`, `/proc`, etc. mais partir d'un point de montage
  type `/mnt` (configurable via `ALLOWED_BROWSE_ROOTS`)

### Frontend — explorateur de dossiers

Composant Alpine.js :

```html
<div x-data="folderBrowser('/mnt')">
  <div class="flex items-center gap-2 mb-2">
    <span class="text-sm font-mono text-gray-600" x-text="currentPath"></span>
  </div>
  <div class="border rounded overflow-hidden">
    <template x-for="dir in directories">
      <div class="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer border-b last:border-b-0"
           @click="navigate(dir.path)">

        <svg class="w-4 h-4 text-amber-500 mr-2">...</svg>
        <span x-text="dir.name" class="text-sm"></span>

        <button class="ml-auto text-xs text-blue-600 hover:underline"
                @click.stop="$dispatch('select-folder', dir.path)">
          Sélectionner
        </button>
      </div>
    </template>
  </div>
  <button x-show="canGoUp" @click="goUp()" class="text-sm mt-1 text-gray-500">
    ↑ Dossier parent
  </button>
</div>
```

### Intégration dans la page de configuration

La page `config.html` contient un formulaire divisé en sections :

1. **Radarr** : URL, clé API, conteneur
2. **Radarr — Bibliothèques** : liste de chemins avec bouton "+" ouvrant
   l'explorateur, bouton "Tester la connexion"
3. **Sonarr** : URL, clé API, conteneur
4. **Sonarr — Bibliothèques** : même pattern
5. **Préfixes surveillés** : liste de patterns (ex: `/mnt/union/debrid/`)
6. **Discord** : activation, webhook, options
7. **Valeurs par défaut** : limite fichiers, rescan, recherche, suppression locale

### Stockage

La configuration est stockée dans un fichier JSON côté serveur
(`data/config.json`), avec un rechargement automatique au démarrage
et à chaque modification depuis l'interface.

Format :

```json
{
  "radarr": {
    "url": "http://radarr:7878",
    "api_key": "",
    "container": "radarr",
    "library_roots": ["/mnt/userdata/radarr/movies"],
    "monitored_prefixes": ["/mnt/union/debrid"]
  },
  "sonarr": {
    "url": "http://sonarr:8989",
    "api_key": "",
    "container": "sonarr",
    "library_roots": ["/mnt/userdata/sonarr/series"],
    "monitored_prefixes": ["/mnt/union/debrid"]
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

### Sécurité

- Les clés API ne sont jamais affichées en clair dans les templates
- L'explorateur refuse les chemins hors des `browse_roots` autorisés
- Les actions destructives nécessitent une confirmation en 2 étapes
