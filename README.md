# SymlinkRepair

**Repérez et réparez les symlinks cassés dans vos bibliothèques Radarr et Sonarr.**

## Pourquoi cet outil ?

Vous utilisez Radarr et Sonarr avec un débrideur (AllDebrid, RealDebrid…) monté via rclone/mergerfs ?  
Vous avez déjà remarqué des fichiers introuvables, des symlinks qui pointent vers rien, des médias qui ne se lancent pas ?

SymlinkRepair scanne vos bibliothèques, détecte les symlinks cassés, et vous permet de les traiter — automatiquement ou manuellement — en quelques clics.

## En un clin d'œil

```
1. Configurer  →  URL et clé API de vos serveurs Radarr/Sonarr
2. Scanner     →  Analyse de vos bibliothèques
3. Traiter     →  Suppression + recherche automatique de remplacement
```

## Démarrage rapide

```bash
docker compose up --build -d
```

Ouvrez **http://localhost:8000**.

> Les dossiers contenant vos médias doivent être accessibles depuis le conteneur.
> Éditez la section `volumes` du `docker-compose.yml` pour ajouter vos montages :

```yaml
services:
  app:
    build: .
    ports:
      - "${PORT:-8000}:8000"
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      # Remplacez /mnt par le chemin de vos bibliothèques médias :
      - /mnt:/mnt
      # - /home/votreuser/medias:/home/votreuser/medias
      - /var/run/docker.sock:/var/run/docker.sock
    env_file: .env
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/symlinkrepair.db
      - DATA_DIR=/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

## Configuration initiale

1. Allez dans **Paramètres** (⚙️)
2. Renseignez l'URL et la clé API de vos serveurs Radarr et Sonarr
3. Cliquez sur **Tester** pour vérifier la connexion
4. Ajoutez les dossiers de vos bibliothèques
5. Sauvegardez

## Utilisation

| Page | À quoi ça sert |
|------|----------------|
| **Dashboard** | Vue d'ensemble : nombre de scans, résultats cassés, taux de résolution, évolution dans le temps |
| **Scan** | Lancer une analyse (complète ou rapide) sur Radarr et/ou Sonarr |
| **Résultats** | Liste des problèmes détectés — traiter, ignorer, revérifier ou marquer comme corrigé |
| **Rapports** | Historique des scans exécutés |
| **Paramètres** | Configuration des serveurs, notifications, scans automatiques |

## Aller plus loin

La documentation détaillée se trouve dans le dossier `docs/`.

---

SymlinkRepair est un outil open-source. Pour signaler un bug ou proposer une amélioration, ouvrez une issue sur le dépôt.
