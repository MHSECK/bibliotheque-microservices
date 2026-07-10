# Bibliothèque Numérique

Projet réalisé dans le cadre de l'examen pratique **Containers et Virtualisation (L2 DIT)**.

Plateforme de gestion de bibliothèque numérique, entièrement **conteneurisée avec Docker / Docker Compose**, et déployée via un pipeline **CI/CD Jenkins**.

---

## 1. Architecture

```
                          ┌─────────────────────┐
                          │      Frontend        │
                          │  Nginx (port 8080)   │
                          │  HTML / CSS / JS     │
                          └──────────┬───────────┘
                                     │ fetch()
                                     ▼
                          ┌─────────────────────┐
                          │       Backend         │
                          │  Flask (port 5001)    │
                          │  /livres /utilisateurs │
                          │  /emprunts             │
                          └──────────┬───────────┘
                                     │ psycopg2
                                     ▼
                          ┌─────────────────────┐
                          │      PostgreSQL       │
                          │      port 5432         │
                          └─────────────────────┘
```

- **3 conteneurs** connectés au même réseau Docker (`reseau-bibliotheque`) : `postgres`, `backend`, `frontend`.
- Un **seul service Flask** (`backend/app.py`) gère les trois domaines métier — livres, utilisateurs, emprunts — chacun sur son propre préfixe de route et sa propre table, dans la **même base PostgreSQL**.
- Lors d'un emprunt ou d'un retour, la mise à jour de la disponibilité du livre se fait par un appel de fonction interne (même processus, même transaction), et non plus par une requête HTTP entre conteneurs.
- Le **frontend** appelle l'API backend via `fetch()` (CORS activé côté Flask).

---

## 2. Structure du dépôt

```
bibliotheque-microservices/
├── backend/                 # API Flask unique - livres, utilisateurs, emprunts (port 5001)
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Interface web statique servie par Nginx (port 8080)
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── Dockerfile
├── docker-compose.yml       # Orchestration des 3 conteneurs
├── Jenkinsfile               # Pipeline CI/CD
└── README.md
```

---

## 3. Fonctionnalités de l'API

### Livres (`/livres`)
| Méthode | Route                             | Description                                  |
|---------|------------------------------------|-----------------------------------------------|
| GET     | `/livres`                          | Liste tous les livres                         |
| GET     | `/livres?titre=&auteur=&isbn=`     | Recherche par titre, auteur ou ISBN           |
| GET     | `/livres/<id>`                     | Détail d'un livre                             |
| POST    | `/livres`                          | Ajouter un livre                              |
| PUT     | `/livres/<id>`                     | Modifier un livre                             |
| DELETE  | `/livres/<id>`                     | Supprimer un livre                            |

Champs : `id`, `titre`, `auteur`, `isbn`, `disponible` (booléen). Un catalogue de 8 livres réels est inséré automatiquement au premier démarrage si la table est vide.

### Utilisateurs (`/utilisateurs`)
| Méthode | Route                  | Description                    |
|---------|-------------------------|---------------------------------|
| GET     | `/utilisateurs`         | Liste tous les utilisateurs     |
| GET     | `/utilisateurs/<id>`    | Profil d'un utilisateur         |
| POST    | `/utilisateurs`         | Créer un utilisateur            |

Champs : `id`, `nom`, `email`, `type` (`Etudiant`, `Professeur`, `Personnel administratif`).

### Emprunts (`/emprunts`)
| Méthode | Route                    | Description                                          |
|---------|---------------------------|--------------------------------------------------------|
| GET     | `/emprunts`               | Historique complet des emprunts                       |
| POST    | `/emprunts`                | Emprunter un livre (marque le livre indisponible)      |
| PUT     | `/emprunts/<id>/retour`   | Retourner un livre (le remarque disponible)            |

Champs : `id`, `id_livre`, `id_utilisateur`, `date_emprunt`, `date_retour`.

---

## 4. Installation et lancement

### Prérequis
- Docker
- Docker Compose (intégré à Docker Desktop ou `docker compose` en CLI)

### Lancer toute la plateforme

Depuis la racine du projet (`bibliotheque-microservices/`) :

```bash
docker-compose up --build
```

Cette commande unique :
1. construit les 2 images Docker (backend Flask + frontend Nginx),
2. démarre PostgreSQL et attend qu'il soit prêt (`healthcheck`),
3. démarre le backend, qui crée automatiquement ses tables au démarrage,
4. démarre le frontend.

### Accès aux services

| Service                | URL                         |
|-------------------------|------------------------------|
| Frontend (interface web)| http://localhost:8080        |
| Backend (API)            | http://localhost:5001        |
| PostgreSQL                | localhost:5432               |

### Arrêter la plateforme

```bash
docker-compose down
```

Pour supprimer aussi les données PostgreSQL persistées :

```bash
docker-compose down -v
```

---

## 5. Pipeline CI/CD (Jenkins)

Le fichier `Jenkinsfile` définit un pipeline déclaratif avec les étapes suivantes :

1. **Checkout** : récupération du code source depuis le dépôt GitHub.
2. **Build des images Docker** : `docker compose build` construit les images des 2 conteneurs applicatifs.
3. **Déploiement** : `docker compose up -d` démarre (ou met à jour) la stack complète en arrière-plan.
4. **Vérification** : `docker compose ps` liste les conteneurs actifs pour confirmer le déploiement.

Un bloc `post` affiche un message de succès ou d'échec selon le résultat du pipeline.

### Configuration dans Jenkins
1. Créer un nouveau job de type **Pipeline**.
2. Dans la section *Pipeline*, choisir **Pipeline script from SCM**, pointer vers le dépôt GitHub du projet et indiquer `Jenkinsfile` comme script path.
3. L'agent Jenkins doit avoir Docker et Docker Compose installés et accessibles.
4. Lancer un build : le pipeline récupère le code, construit les images, puis déploie la stack.

---

## 6. Détails techniques

- **Connexion base de données** : le backend utilise `psycopg2` et lit ses paramètres de connexion (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) depuis des variables d'environnement définies dans `docker-compose.yml`.
- **Création automatique des tables** : le backend exécute `CREATE TABLE IF NOT EXISTS` pour les trois tables au démarrage, avec un mécanisme de nouvelles tentatives (retry) au cas où PostgreSQL ne serait pas encore prêt — aucune étape manuelle n'est nécessaire.
- **CORS** : activé via `flask-cors` pour permettre au frontend de l'appeler depuis une origine différente.
- **Persistance** : le volume nommé `postgres_data` conserve les données PostgreSQL même après un `docker-compose down` (sans `-v`).
- **Gestion des erreurs** : l'API renvoie des codes HTTP appropriés (`400` données invalides, `404` ressource introuvable, `409` conflit — ex. livre déjà emprunté/email déjà utilisé).

---

## 7. Auteur

Projet réalisé dans le cadre de l'examen pratique **Containers et Virtualisation — L2 DIT**.
