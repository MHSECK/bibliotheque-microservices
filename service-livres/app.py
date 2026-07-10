"""
Service Livres - API REST pour la gestion du catalogue de livres.
Fournit : ajout, modification, suppression, listing et recherche de livres.
Expose aussi une route interne (/livres/<id>/disponibilite) utilisée par
le service Emprunts pour marquer un livre disponible/indisponible.
"""

import os
import time

import psycopg2
import psycopg2.extras
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


def get_connection():
    """Ouvre une nouvelle connexion PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


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


def init_db():
    """
    Crée la table 'livres' si elle n'existe pas encore, et la peuple avec
    un catalogue de démarrage si elle est vide. On réessaie plusieurs fois
    car PostgreSQL peut mettre quelques secondes à être prêt au démarrage
    de docker-compose.
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
            conn.commit()

            cur.execute("SELECT COUNT(*) FROM livres;")
            (nombre_livres,) = cur.fetchone()
            if nombre_livres == 0:
                cur.executemany(
                    "INSERT INTO livres (titre, auteur, isbn, disponible) VALUES (%s, %s, %s, %s);",
                    LIVRES_INITIAUX,
                )
                conn.commit()
                print(f"[service-livres] {len(LIVRES_INITIAUX)} livres de démarrage insérés.")

            cur.close()
            conn.close()
            print("[service-livres] Table 'livres' prête.")
            return
        except psycopg2.OperationalError as e:
            print(f"[service-livres] PostgreSQL indisponible ({e}), nouvelle tentative dans 3s...")
            time.sleep(3)
    raise RuntimeError("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")


def livre_vers_dict(row):
    """Convertit une ligne SQL (tuple) en dictionnaire JSON-friendly."""
    return {
        "id": row[0],
        "titre": row[1],
        "auteur": row[2],
        "isbn": row[3],
        "disponible": row[4],
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "service-livres"}), 200


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


@app.route("/livres/<int:livre_id>/disponibilite", methods=["PUT"])
def changer_disponibilite(livre_id):
    """
    Route interne appelée par le service Emprunts pour marquer
    un livre disponible (True) ou indisponible (False).
    """
    donnees = request.get_json(silent=True) or {}
    disponible = donnees.get("disponible")

    if disponible is None or not isinstance(disponible, bool):
        return jsonify({"erreur": "Champ booléen 'disponible' requis"}), 400

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE livres SET disponible = %s
        WHERE id = %s
        RETURNING id, titre, auteur, isbn, disponible;
        """,
        (disponible, livre_id),
    )
    livre_maj = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if livre_maj is None:
        return jsonify({"erreur": "Livre introuvable"}), 404

    return jsonify(livre_vers_dict(livre_maj)), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001)
