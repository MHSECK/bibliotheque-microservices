# Bibliothèque Numérique — Plateforme Microservices

Projet réalisé dans le cadre de l'examen pratique **Containers et Virtualisation (L2 DIT)**.

Plateforme de gestion de bibliothèque numérique construite en **architecture microservices**, entièrement **conteneurisée avec Docker / Docker Compose**, et déployée via un pipeline **CI/CD Jenkins**.

---

## 1. Architecture

```
                          ┌─────────────────────┐
                          │      Frontend        │
                          │  Nginx (port 8080)   │
                          │  HTML / CSS / JS     │
                          └─────┬───────┬───────┘
                     fetch()    │       │      fetch()
              ┌─────────────────┘       └─────────────────┐
              │                                             │
   ┌──────────▼──────────┐                       ┌──────────▼──────────┐
   │   service-livres     │                       │ service-utilisateurs │
   │  Flask (port 5001)   │                       │   Flask (port 5002)  │
   └──────────┬──────────┘                       └──────────┬──────────┘
              │                                             │
              │            ┌──────────────────────┐         │
              └───────────►│   service-emprunts    │◄────────┘
                HTTP        │   Flask (port 5003)   │
             (requests)     └──────────┬───────────┘
                                        │
                              ┌─────────▼─────────┐
                              │     PostgreSQL      │
                              │     port 5432        │
                              └──────────────────────┘
```

- **5 conteneurs** connectés au même réseau Docker (`reseau-bibliotheque`) : `postgres`, `service-livres`, `service-utilisateurs`, `service-emprunts`, `frontend`.
- Une **seule base PostgreSQL** partagée, avec une table par service (`livres`, `utilisateurs`, `emprunts`).
- Le **service Emprunts** communique avec le **service Livres via HTTP** (librairie `requests`) pour marquer un livre disponible/indisponible lors d'un emprunt ou d'un retour — c'est la communication inter-services du projet.
- Le **frontend** appelle directement les 3 APIs backend via `fetch()` (CORS activé sur chaque service Flask).

---

## 2. Structure du dépôt

```
bibliotheque-microservices/
├── service-livres/         # API Flask - gestion des livres (port 5001)
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── service-utilisateurs/   # API Flask - gestion des utilisateurs (port 5002)
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── service-emprunts/       # API Flask - gestion des emprunts (port 5003)
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Interface web statique servie par Nginx (port 8080)
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── Dockerfile
├── docker-compose.yml       # Orchestration des 5 conteneurs
├── Jenkinsfile               # Pipeline CI/CD
└── README.md
```

---

## 3. Fonctionnalités

### Service Livres (`/livres`)
| Méthode | Route                             | Description                                  |
|---------|------------------------------------|-----------------------------------------------|
| GET     | `/livres`                          | Liste tous les livres                         |
| GET     | `/livres?titre=&auteur=&isbn=`     | Recherche par titre, auteur ou ISBN           |
| GET     | `/livres/<id>`                     | Détail d'un livre                             |
| POST    | `/livres`                          | Ajouter un livre                              |
| PUT     | `/livres/<id>`                     | Modifier un livre                             |
| DELETE  | `/livres/<id>`                     | Supprimer un livre                            |
| PUT     | `/livres/<id>/disponibilite`       | (interne) Changer la disponibilité d'un livre |

Champs : `id`, `titre`, `auteur`, `isbn`, `disponible` (booléen).

### Service Utilisateurs (`/utilisateurs`)
| Méthode | Route                  | Description                    |
|---------|-------------------------|---------------------------------|
| GET     | `/utilisateurs`         | Liste tous les utilisateurs     |
| GET     | `/utilisateurs/<id>`    | Profil d'un utilisateur         |
| POST    | `/utilisateurs`         | Créer un utilisateur            |

Champs : `id`, `nom`, `email`, `type` (`Etudiant`, `Professeur`, `Personnel administratif`).

### Service Emprunts (`/emprunts`)
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
1. construit les 4 images Docker (3 services Flask + frontend Nginx),
2. démarre PostgreSQL et attend qu'il soit prêt (`healthcheck`),
3. démarre les 3 microservices, chacun créant automatiquement sa table au démarrage,
4. démarre le frontend.

### Accès aux services

| Service                | URL                         |
|-------------------------|------------------------------|
| Frontend (interface web)| http://localhost:8080        |
| Service Livres           | http://localhost:5001/livres |
| Service Utilisateurs     | http://localhost:5002/utilisateurs |
| Service Emprunts         | http://localhost:5003/emprunts |
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
2. **Build des images Docker** : `docker compose build` construit les images des 4 conteneurs applicatifs.
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

- **Connexion base de données** : chaque service Flask utilise `psycopg2` et lit ses paramètres de connexion (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) depuis des variables d'environnement définies dans `docker-compose.yml`.
- **Création automatique des tables** : chaque service exécute `CREATE TABLE IF NOT EXISTS` au démarrage, avec un mécanisme de nouvelles tentatives (retry) au cas où PostgreSQL ne serait pas encore prêt — aucune étape manuelle n'est nécessaire.
- **CORS** : activé via `flask-cors` sur les 3 services pour permettre au frontend de les appeler depuis une origine différente.
- **Communication inter-services** : `service-emprunts` appelle `service-livres` via HTTP (`requests`), en utilisant le nom du service Docker Compose (`http://service-livres:5001`) comme nom DNS interne au réseau `reseau-bibliotheque`.
- **Persistance** : le volume nommé `postgres_data` conserve les données PostgreSQL même après un `docker-compose down` (sans `-v`).
- **Gestion des erreurs** : les APIs renvoient des codes HTTP appropriés (`400` données invalides, `404` ressource introuvable, `409` conflit — ex. livre déjà emprunté/email déjà utilisé, `503`/`502` service injoignable).

---

## 7. Auteur

Projet réalisé dans le cadre de l'examen pratique **Containers et Virtualisation — L2 DIT**.
