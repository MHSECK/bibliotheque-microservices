/**
 * Frontend JavaScript pur (aucun framework).
 * Communique avec les 3 microservices via fetch().
 *
 * Les services backend sont exposés directement sur l'hôte par
 * docker-compose (ports 5001/5002/5003), donc le navigateur les
 * appelle en HTTP direct depuis la même machine que le frontend.
 */

const HOTE = window.location.hostname;
const API_LIVRES = `http://${HOTE}:5001`;
const API_UTILISATEURS = `http://${HOTE}:5002`;
const API_EMPRUNTS = `http://${HOTE}:5003`;

// ============================================================
// Gestion des onglets
// ============================================================
document.querySelectorAll(".onglet-btn").forEach((bouton) => {
  bouton.addEventListener("click", () => {
    document.querySelectorAll(".onglet-btn").forEach((b) => b.classList.remove("actif"));
    document.querySelectorAll(".onglet-contenu").forEach((c) => c.classList.remove("actif"));

    bouton.classList.add("actif");
    document.getElementById(bouton.dataset.cible).classList.add("actif");
  });
});

// ============================================================
// Utilitaire d'affichage de message (succès / erreur)
// ============================================================
function afficherMessage(elementId, texte, type) {
  const el = document.getElementById(elementId);
  el.textContent = texte;
  el.className = `message ${type}`;
  setTimeout(() => {
    el.textContent = "";
    el.className = "message";
  }, 4000);
}

// ============================================================
// SECTION LIVRES
// ============================================================
const formLivre = document.getElementById("form-livre");
const tableauLivres = document.getElementById("tableau-livres");

async function chargerLivres(params = {}) {
  const query = new URLSearchParams(params).toString();
  try {
    const reponse = await fetch(`${API_LIVRES}/livres${query ? "?" + query : ""}`);
    const livres = await reponse.json();

    tableauLivres.innerHTML = "";
    livres.forEach((livre) => {
      const ligne = document.createElement("tr");
      ligne.innerHTML = `
        <td>${livre.id}</td>
        <td>${livre.titre}</td>
        <td>${livre.auteur}</td>
        <td>${livre.isbn}</td>
        <td class="${livre.disponible ? "disponible-oui" : "disponible-non"}">
          ${livre.disponible ? "Oui" : "Non"}
        </td>
        <td>
          <button onclick="modifierLivreFormulaire(${livre.id}, '${livre.titre.replace(/'/g, "\\'")}', '${livre.auteur.replace(/'/g, "\\'")}', '${livre.isbn}')">Éditer</button>
          <button class="danger" onclick="supprimerLivre(${livre.id})">Supprimer</button>
        </td>
      `;
      tableauLivres.appendChild(ligne);
    });
  } catch (erreur) {
    afficherMessage("message-livres", "Impossible de contacter le service Livres.", "erreur");
  }
}

formLivre.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();

  const id = document.getElementById("livre-id").value;
  const corps = {
    titre: document.getElementById("livre-titre").value,
    auteur: document.getElementById("livre-auteur").value,
    isbn: document.getElementById("livre-isbn").value,
  };

  try {
    const reponse = await fetch(`${API_LIVRES}/livres${id ? "/" + id : ""}`, {
      method: id ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    });
    const resultat = await reponse.json();

    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur inconnue");

    afficherMessage("message-livres", id ? "Livre modifié avec succès." : "Livre ajouté avec succès.", "succes");
    formLivre.reset();
    document.getElementById("livre-id").value = "";
    chargerLivres();
  } catch (erreur) {
    afficherMessage("message-livres", erreur.message, "erreur");
  }
});

document.getElementById("livre-annuler").addEventListener("click", () => {
  formLivre.reset();
  document.getElementById("livre-id").value = "";
});

function modifierLivreFormulaire(id, titre, auteur, isbn) {
  document.getElementById("livre-id").value = id;
  document.getElementById("livre-titre").value = titre;
  document.getElementById("livre-auteur").value = auteur;
  document.getElementById("livre-isbn").value = isbn;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function supprimerLivre(id) {
  if (!confirm("Confirmer la suppression de ce livre ?")) return;
  try {
    const reponse = await fetch(`${API_LIVRES}/livres/${id}`, { method: "DELETE" });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur inconnue");

    afficherMessage("message-livres", "Livre supprimé.", "succes");
    chargerLivres();
  } catch (erreur) {
    afficherMessage("message-livres", erreur.message, "erreur");
  }
}

document.getElementById("btn-rechercher").addEventListener("click", () => {
  chargerLivres({
    titre: document.getElementById("recherche-titre").value,
    auteur: document.getElementById("recherche-auteur").value,
    isbn: document.getElementById("recherche-isbn").value,
  });
});

document.getElementById("btn-reset-recherche").addEventListener("click", () => {
  document.getElementById("recherche-titre").value = "";
  document.getElementById("recherche-auteur").value = "";
  document.getElementById("recherche-isbn").value = "";
  chargerLivres();
});

// ============================================================
// SECTION UTILISATEURS
// ============================================================
const formUtilisateur = document.getElementById("form-utilisateur");
const tableauUtilisateurs = document.getElementById("tableau-utilisateurs");

async function chargerUtilisateurs() {
  try {
    const reponse = await fetch(`${API_UTILISATEURS}/utilisateurs`);
    const utilisateurs = await reponse.json();

    tableauUtilisateurs.innerHTML = "";
    utilisateurs.forEach((u) => {
      const ligne = document.createElement("tr");
      ligne.innerHTML = `
        <td>${u.id}</td><td>${u.nom}</td><td>${u.email}</td><td>${u.type}</td>
      `;
      tableauUtilisateurs.appendChild(ligne);
    });
  } catch (erreur) {
    afficherMessage("message-utilisateurs", "Impossible de contacter le service Utilisateurs.", "erreur");
  }
}

formUtilisateur.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();

  const corps = {
    nom: document.getElementById("utilisateur-nom").value,
    email: document.getElementById("utilisateur-email").value,
    type: document.getElementById("utilisateur-type").value,
  };

  try {
    const reponse = await fetch(`${API_UTILISATEURS}/utilisateurs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur inconnue");

    afficherMessage("message-utilisateurs", "Utilisateur créé avec succès.", "succes");
    formUtilisateur.reset();
    chargerUtilisateurs();
  } catch (erreur) {
    afficherMessage("message-utilisateurs", erreur.message, "erreur");
  }
});

// ============================================================
// SECTION EMPRUNTS
// ============================================================
const formEmprunt = document.getElementById("form-emprunt");
const tableauEmprunts = document.getElementById("tableau-emprunts");

async function chargerEmprunts() {
  try {
    const reponse = await fetch(`${API_EMPRUNTS}/emprunts`);
    const emprunts = await reponse.json();

    tableauEmprunts.innerHTML = "";
    emprunts.forEach((e) => {
      const ligne = document.createElement("tr");
      const dejaRetourne = e.date_retour !== null;
      ligne.innerHTML = `
        <td>${e.id}</td>
        <td>${e.id_livre}</td>
        <td>${e.id_utilisateur}</td>
        <td>${new Date(e.date_emprunt).toLocaleString("fr-FR")}</td>
        <td>${dejaRetourne ? new Date(e.date_retour).toLocaleString("fr-FR") : "—"}</td>
        <td>
          ${dejaRetourne ? "" : `<button onclick="retournerLivre(${e.id})">Marquer retourné</button>`}
        </td>
      `;
      tableauEmprunts.appendChild(ligne);
    });
  } catch (erreur) {
    afficherMessage("message-emprunts", "Impossible de contacter le service Emprunts.", "erreur");
  }
}

formEmprunt.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();

  const corps = {
    id_livre: parseInt(document.getElementById("emprunt-id-livre").value, 10),
    id_utilisateur: parseInt(document.getElementById("emprunt-id-utilisateur").value, 10),
  };

  try {
    const reponse = await fetch(`${API_EMPRUNTS}/emprunts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur inconnue");

    afficherMessage("message-emprunts", "Emprunt enregistré avec succès.", "succes");
    formEmprunt.reset();
    chargerEmprunts();
    chargerLivres(); // Le livre passe indisponible, on rafraîchit la liste
  } catch (erreur) {
    afficherMessage("message-emprunts", erreur.message, "erreur");
  }
});

async function retournerLivre(idEmprunt) {
  try {
    const reponse = await fetch(`${API_EMPRUNTS}/emprunts/${idEmprunt}/retour`, {
      method: "PUT",
    });
    const resultat = await reponse.json();
    if (!reponse.ok) throw new Error(resultat.erreur || "Erreur inconnue");

    afficherMessage("message-emprunts", "Livre retourné avec succès.", "succes");
    chargerEmprunts();
    chargerLivres(); // Le livre redevient disponible, on rafraîchit la liste
  } catch (erreur) {
    afficherMessage("message-emprunts", erreur.message, "erreur");
  }
}

// ============================================================
// Chargement initial des données au démarrage de la page
// ============================================================
chargerLivres();
chargerUtilisateurs();
chargerEmprunts();
