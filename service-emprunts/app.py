"""
Service Emprunts - API REST pour la gestion des emprunts de livres.

Ce service communique avec le service Livres via HTTP (requests) :
- lors d'un emprunt, il vérifie que le livre est disponible puis
  demande au service Livres de le marquer indisponible.
- lors d'un retour, il demande au service Livres de remarquer
  le livre disponible.
C'est la communication inter-services (Emprunts -> Livres) demandée.
"""

import os
import time
from datetime import datetime

import psycopg2
import requests
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

# URL du service Livres, injectée par docker-compose (nom du service = nom DNS interne)
SERVICE_LIVRES_URL = os.environ.get("SERVICE_LIVRES_URL", "http://service-livres:5001")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():
    """Crée la table 'emprunts' si elle n'existe pas, avec retry au démarrage."""
    tentatives = 10
    for _ in range(tentatives):
        try:
            conn = get_connection()
            cur = conn.cursor()
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
            cur.close()
            conn.close()
            print("[service-emprunts] Table 'emprunts' prête.")
            return
        except psycopg2.OperationalError as e:
            print(f"[service-emprunts] PostgreSQL indisponible ({e}), nouvelle tentative dans 3s...")
            time.sleep(3)
    raise RuntimeError("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")


def emprunt_vers_dict(row):
    return {
        "id": row[0],
        "id_livre": row[1],
        "id_utilisateur": row[2],
        "date_emprunt": row[3].isoformat() if row[3] else None,
        "date_retour": row[4].isoformat() if row[4] else None,
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "service-emprunts"}), 200


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
    Emprunte un livre :
    1. Vérifie auprès du service Livres que le livre existe et est disponible.
    2. Enregistre l'emprunt en base.
    3. Demande au service Livres de marquer le livre indisponible.
    """
    donnees = request.get_json(silent=True) or {}
    id_livre = donnees.get("id_livre")
    id_utilisateur = donnees.get("id_utilisateur")

    if not id_livre or not id_utilisateur:
        return jsonify({"erreur": "Champs 'id_livre' et 'id_utilisateur' requis"}), 400

    # --- Appel HTTP au service Livres pour vérifier la disponibilité ---
    try:
        reponse = requests.get(f"{SERVICE_LIVRES_URL}/livres/{id_livre}", timeout=5)
    except requests.exceptions.RequestException:
        return jsonify({"erreur": "Service Livres injoignable"}), 503

    if reponse.status_code == 404:
        return jsonify({"erreur": "Livre introuvable"}), 404
    if reponse.status_code != 200:
        return jsonify({"erreur": "Erreur lors de la vérification du livre"}), 502

    livre = reponse.json()
    if not livre.get("disponible", False):
        return jsonify({"erreur": "Ce livre n'est pas disponible actuellement"}), 409

    # --- Enregistrement de l'emprunt ---
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO emprunts (id_livre, id_utilisateur, date_emprunt, date_retour)
        VALUES (%s, %s, %s, NULL)
        RETURNING id, id_livre, id_utilisateur, date_emprunt, date_retour;
        """,
        (id_livre, id_utilisateur, datetime.now()),
    )
    nouvel_emprunt = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    # --- Appel HTTP au service Livres pour marquer le livre indisponible ---
    try:
        requests.put(
            f"{SERVICE_LIVRES_URL}/livres/{id_livre}/disponibilite",
            json={"disponible": False},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        # L'emprunt est déjà enregistré ; on signale l'incident sans le bloquer.
        print(f"[service-emprunts] Attention : échec de mise à jour de la disponibilité du livre {id_livre}")

    return jsonify(emprunt_vers_dict(nouvel_emprunt)), 201


@app.route("/emprunts/<int:emprunt_id>/retour", methods=["PUT"])
def retourner_livre(emprunt_id):
    """
    Retourne un livre emprunté :
    1. Vérifie que l'emprunt existe et n'est pas déjà retourné.
    2. Met à jour la date de retour.
    3. Demande au service Livres de remarquer le livre disponible.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, id_livre, id_utilisateur, date_emprunt, date_retour "
        "FROM emprunts WHERE id = %s;",
        (emprunt_id,),
    )
    emprunt = cur.fetchone()

    if emprunt is None:
        cur.close()
        conn.close()
        return jsonify({"erreur": "Emprunt introuvable"}), 404

    if emprunt[4] is not None:
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
    conn.commit()
    cur.close()
    conn.close()

    # --- Appel HTTP au service Livres pour remarquer le livre disponible ---
    try:
        requests.put(
            f"{SERVICE_LIVRES_URL}/livres/{id_livre}/disponibilite",
            json={"disponible": True},
            timeout=5,
        )
    except requests.exceptions.RequestException:
        print(f"[service-emprunts] Attention : échec de mise à jour de la disponibilité du livre {id_livre}")

    return jsonify(emprunt_vers_dict(emprunt_maj)), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5003)
