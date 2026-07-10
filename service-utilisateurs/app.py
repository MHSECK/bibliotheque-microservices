"""
Service Utilisateurs - API REST pour la gestion des utilisateurs
de la bibliothèque (Etudiant, Professeur, Personnel administratif).
"""

import os
import time

import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Configuration de la connexion PostgreSQL via variables d'environnement ---
DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "bibliotheque")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

# Types d'utilisateur autorisés
TYPES_VALIDES = ["Etudiant", "Professeur", "Personnel administratif"]


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():
    """Crée la table 'utilisateurs' si elle n'existe pas, avec retry au démarrage."""
    tentatives = 10
    for _ in range(tentatives):
        try:
            conn = get_connection()
            cur = conn.cursor()
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
            conn.commit()
            cur.close()
            conn.close()
            print("[service-utilisateurs] Table 'utilisateurs' prête.")
            return
        except psycopg2.OperationalError as e:
            print(f"[service-utilisateurs] PostgreSQL indisponible ({e}), nouvelle tentative dans 3s...")
            time.sleep(3)
    raise RuntimeError("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")


def utilisateur_vers_dict(row):
    return {
        "id": row[0],
        "nom": row[1],
        "email": row[2],
        "type": row[3],
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "service-utilisateurs"}), 200


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

    if type_utilisateur not in TYPES_VALIDES:
        return jsonify(
            {"erreur": f"Type invalide. Valeurs autorisées : {', '.join(TYPES_VALIDES)}"}
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


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5002)
