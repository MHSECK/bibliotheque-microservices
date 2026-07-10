"""
Backend unique de la Bibliothèque Numérique.
Regroupe dans un seul service Flask la gestion des livres, des utilisateurs
et des emprunts (auparavant trois microservices séparés). Les trois
domaines restent isolés par préfixe de route et par table, mais partagent
le même processus et la même connexion PostgreSQL : le passage d'un livre
à l'état indisponible lors d'un emprunt se fait donc par un appel de
fonction interne, plus par une requête HTTP entre conteneurs.
"""

import os
import time
from datetime import datetime

import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Autorise le frontend (autre origine) à appeler cette API

# --- Configuration de la connexion PostgreSQL via variables d'environnement ---
DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "bibliotheque")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

TYPES_UTILISATEUR_VALIDES = ["Etudiant", "Professeur", "Personnel administratif"]

# Catalogue de démarrage : quelques classiques réels pour ne pas partir
# d'une base vide à la première installation (deux titres démarrent
# indisponibles pour illustrer l'état "emprunté" dans l'interface).
LIVRES_INITIAUX = [
    ("1984", "George Orwell", "978-2070368228", True),
    ("Le Petit Prince", "Antoine de Saint-Exupéry", "978-2070408504", True),
    ("Les Misérables", "Victor Hugo", "978-2253096374", False),
    ("L'Étranger", "Albert Camus", "978-2070360024", True),
    ("Harry Potter à l'école des sorciers", "J.K. Rowling", "978-2070518514", True),
    ("Le Seigneur des Anneaux", "J.R.R. Tolkien", "978-2266154116", False),
    ("Candide", "Voltaire", "978-2081221415", True),
    ("Les Fleurs du mal", "Charles Baudelaire", "978-2080712066", True),
]


def get_connection():
    """Ouvre une nouvelle connexion PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():
    """
    Crée les tables 'livres', 'utilisateurs' et 'emprunts' si elles
    n'existent pas encore, et peuple 'livres' avec un catalogue de
    démarrage si elle est vide. On réessaie plusieurs fois car PostgreSQL
    peut mettre quelques secondes à être prêt au démarrage de docker-compose.
    """
    tentatives = 10
    for _ in range(tentatives):
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS livres (
                    id SERIAL PRIMARY KEY,
                    titre VARCHAR(255) NOT NULL,
                    auteur VARCHAR(255) NOT NULL,
                    isbn VARCHAR(50) NOT NULL,
                    disponible BOOLEAN NOT NULL DEFAULT TRUE
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS utilisateurs (
                    id SERIAL PRIMARY KEY,
                    nom VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    type VARCHAR(50) NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS emprunts (
                    id SERIAL PRIMARY KEY,
                    id_livre INTEGER NOT NULL,
                    id_utilisateur INTEGER NOT NULL,
                    date_emprunt TIMESTAMP NOT NULL,
                    date_retour TIMESTAMP
                );
                """
            )
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM livres;")
            (nombre_livres,) = cur.fetchone()
            if nombre_livres == 0:
                cur.executemany(
                    "INSERT INTO livres (titre, auteur, isbn, disponible) VALUES (%s, %s, %s, %s);",
                    LIVRES_INITIAUX,
                )
                conn.commit()
                print(f"[backend] {len(LIVRES_INITIAUX)} livres de démarrage insérés.")

            cur.close()
            conn.close()
            print("[backend] Tables 'livres', 'utilisateurs' et 'emprunts' prêtes.")
            return
        except psycopg2.OperationalError as e:
            print(f"[backend] PostgreSQL indisponible ({e}), nouvelle tentative dans 3s...")
            time.sleep(3)
    raise RuntimeError("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "backend"}), 200


# ============================================================
# LIVRES
# ============================================================
def livre_vers_dict(row):
    return {
        "id": row[0],
        "titre": row[1],
        "auteur": row[2],
        "isbn": row[3],
        "disponible": row[4],
    }


@app.route("/livres", methods=["GET"])
def lister_livres():
    """
    Liste tous les livres. Supporte la recherche via paramètres de requête :
    /livres?titre=...&auteur=...&isbn=...
    La recherche est insensible à la casse et fonctionne par sous-chaîne.
    """
    titre = request.args.get("titre")
    auteur = request.args.get("auteur")
    isbn = request.args.get("isbn")

    conditions = []
    valeurs = []

    if titre:
        conditions.append("titre ILIKE %s")
        valeurs.append(f"%{titre}%")
    if auteur:
        conditions.append("auteur ILIKE %s")
        valeurs.append(f"%{auteur}%")
    if isbn:
        conditions.append("isbn ILIKE %s")
        valeurs.append(f"%{isbn}%")

    requete = "SELECT id, titre, auteur, isbn, disponible FROM livres"
    if conditions:
        requete += " WHERE " + " AND ".join(conditions)
    requete += " ORDER BY id;"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(requete, valeurs)
    lignes = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([livre_vers_dict(l) for l in lignes]), 200


@app.route("/livres/<int:livre_id>", methods=["GET"])
def obtenir_livre(livre_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, titre, auteur, isbn, disponible FROM livres WHERE id = %s;",
        (livre_id,),
    )
    ligne = cur.fetchone()
    cur.close()
    conn.close()

    if ligne is None:
        return jsonify({"erreur": "Livre introuvable"}), 404

    return jsonify(livre_vers_dict(ligne)), 200


@app.route("/livres", methods=["POST"])
def ajouter_livre():
    donnees = request.get_json(silent=True) or {}
    titre = donnees.get("titre")
    auteur = donnees.get("auteur")
    isbn = donnees.get("isbn")
    disponible = donnees.get("disponible", True)

    if not titre or not auteur or not isbn:
        return jsonify({"erreur": "Champs 'titre', 'auteur' et 'isbn' requis"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO livres (titre, auteur, isbn, disponible)
        VALUES (%s, %s, %s, %s)
        RETURNING id, titre, auteur, isbn, disponible;
        """,
        (titre, auteur, isbn, disponible),
    )
    nouveau_livre = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify(livre_vers_dict(nouveau_livre)), 201


@app.route("/livres/<int:livre_id>", methods=["PUT"])
def modifier_livre(livre_id):
    donnees = request.get_json(silent=True) or {}

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM livres WHERE id = %s;", (livre_id,))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Livre introuvable"}), 404

    cur.execute(
        """
        UPDATE livres
        SET titre = COALESCE(%s, titre),
            auteur = COALESCE(%s, auteur),
            isbn = COALESCE(%s, isbn),
            disponible = COALESCE(%s, disponible)
        WHERE id = %s
        RETURNING id, titre, auteur, isbn, disponible;
        """,
        (
            donnees.get("titre"),
            donnees.get("auteur"),
            donnees.get("isbn"),
            donnees.get("disponible"),
            livre_id,
        ),
    )
    livre_maj = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return jsonify(livre_vers_dict(livre_maj)), 200


@app.route("/livres/<int:livre_id>", methods=["DELETE"])
def supprimer_livre(livre_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM livres WHERE id = %s RETURNING id;", (livre_id,))
    supprime = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if supprime is None:
        return jsonify({"erreur": "Livre introuvable"}), 404

    return jsonify({"message": f"Livre {livre_id} supprimé"}), 200


# ============================================================
# UTILISATEURS
# ============================================================
def utilisateur_vers_dict(row):
    return {
        "id": row[0],
        "nom": row[1],
        "email": row[2],
        "type": row[3],
    }


@app.route("/utilisateurs", methods=["GET"])
def lister_utilisateurs():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, nom, email, type FROM utilisateurs ORDER BY id;")
    lignes = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([utilisateur_vers_dict(u) for u in lignes]), 200


@app.route("/utilisateurs/<int:utilisateur_id>", methods=["GET"])
def obtenir_utilisateur(utilisateur_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nom, email, type FROM utilisateurs WHERE id = %s;",
        (utilisateur_id,),
    )
    ligne = cur.fetchone()
    cur.close()
    conn.close()

    if ligne is None:
        return jsonify({"erreur": "Utilisateur introuvable"}), 404

    return jsonify(utilisateur_vers_dict(ligne)), 200


@app.route("/utilisateurs", methods=["POST"])
def creer_utilisateur():
    donnees = request.get_json(silent=True) or {}
    nom = donnees.get("nom")
    email = donnees.get("email")
    type_utilisateur = donnees.get("type")

    if not nom or not email or not type_utilisateur:
        return jsonify({"erreur": "Champs 'nom', 'email' et 'type' requis"}), 400

    if type_utilisateur not in TYPES_UTILISATEUR_VALIDES:
        return jsonify(
            {"erreur": f"Type invalide. Valeurs autorisées : {', '.join(TYPES_UTILISATEUR_VALIDES)}"}
        ), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO utilisateurs (nom, email, type)
            VALUES (%s, %s, %s)
            RETURNING id, nom, email, type;
            """,
            (nom, email, type_utilisateur),
        )
        nouvel_utilisateur = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return jsonify({"erreur": "Un utilisateur avec cet email existe déjà"}), 409
    finally:
        cur.close()
        conn.close()

    return jsonify(utilisateur_vers_dict(nouvel_utilisateur)), 201


# ============================================================
# EMPRUNTS
# ============================================================
def emprunt_vers_dict(row):
    return {
        "id": row[0],
        "id_livre": row[1],
        "id_utilisateur": row[2],
        "date_emprunt": row[3].isoformat() if row[3] else None,
        "date_retour": row[4].isoformat() if row[4] else None,
    }


@app.route("/emprunts", methods=["GET"])
def historique_emprunts():
    """Historique complet des emprunts (en cours + retournés)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, id_livre, id_utilisateur, date_emprunt, date_retour "
        "FROM emprunts ORDER BY id DESC;"
    )
    lignes = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([emprunt_vers_dict(e) for e in lignes]), 200


@app.route("/emprunts", methods=["POST"])
def emprunter_livre():
    """
    Emprunte un livre : vérifie sa disponibilité, enregistre l'emprunt et
    marque le livre indisponible, dans la même transaction PostgreSQL
    (les trois domaines partagent désormais la même connexion).
    """
    donnees = request.get_json(silent=True) or {}
    id_livre = donnees.get("id_livre")
    id_utilisateur = donnees.get("id_utilisateur")

    if not id_livre or not id_utilisateur:
        return jsonify({"erreur": "Champs 'id_livre' et 'id_utilisateur' requis"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT disponible FROM livres WHERE id = %s;", (id_livre,))
    livre = cur.fetchone()
    if livre is None:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Livre introuvable"}), 404
    if not livre[0]:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Ce livre n'est pas disponible actuellement"}), 409

    cur.execute(
        """
        INSERT INTO emprunts (id_livre, id_utilisateur, date_emprunt, date_retour)
        VALUES (%s, %s, %s, NULL)
        RETURNING id, id_livre, id_utilisateur, date_emprunt, date_retour;
        """,
        (id_livre, id_utilisateur, datetime.now()),
    )
    nouvel_emprunt = cur.fetchone()

    cur.execute("UPDATE livres SET disponible = FALSE WHERE id = %s;", (id_livre,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify(emprunt_vers_dict(nouvel_emprunt)), 201


@app.route("/emprunts/<int:emprunt_id>/retour", methods=["PUT"])
def retourner_livre(emprunt_id):
    """
    Retourne un livre emprunté : enregistre la date de retour et remarque
    le livre disponible, dans la même transaction.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, id_livre, date_retour FROM emprunts WHERE id = %s;",
        (emprunt_id,),
    )
    emprunt = cur.fetchone()

    if emprunt is None:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Emprunt introuvable"}), 404

    if emprunt[2] is not None:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Ce livre a déjà été retourné"}), 409

    id_livre = emprunt[1]

    cur.execute(
        """
        UPDATE emprunts SET date_retour = %s
        WHERE id = %s
        RETURNING id, id_livre, id_utilisateur, date_emprunt, date_retour;
        """,
        (datetime.now(), emprunt_id),
    )
    emprunt_maj = cur.fetchone()

    cur.execute("UPDATE livres SET disponible = TRUE WHERE id = %s;", (id_livre,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify(emprunt_vers_dict(emprunt_maj)), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001)
