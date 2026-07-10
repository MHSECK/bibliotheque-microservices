/**
 * Frontend JavaScript pur (aucun framework).
 * Communique avec le backend via fetch().
 *
 * Le backend est exposé directement sur l'hôte par docker-compose
 * (port 5000), donc le navigateur l'appelle en HTTP direct depuis la
 * même machine que le frontend.
 */

const HOTE = window.location.hostname;
const API_BASE = `http://${HOTE}:5001`;
const API_LIVRES = API_BASE;
const API_UTILISATEURS = API_BASE;
const API_EMPRUNTS = API_BASE;

// Caches locales utilisées pour afficher le titre d'un livre / le nom d'un
// utilisateur dans l'historique des emprunts sans multiplier les appels API.
let livresCache = [];
let utilisateursCache = [];

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
// Utilitaires d'affichage
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

function definirChargement(bouton, enCours, texteChargement, texteNormal) {
  bouton.disabled = enCours;
  bouton.textContent = enCours ? texteChargement : texteNormal;
}

function ligneEtatVide(nbColonnes, texte) {
  return `<tr class="etat-vide"><td colspan="${nbColonnes}">${texte}</td></tr>`;
}

function echapperHtml(texte) {
  const div = document.createElement("div");
  div.textContent = texte;
  return div.innerHTML;
}

// ============================================================
// SECTION LIVRES
// ============================================================
const formLivre = document.getElementById("form-livre");
const tableauLivres = document.getElementById("tableau-livres");
const boutonLivreSubmit = document.getElementById("livre-submit");

async function chargerLivres(params = {}) {
  const query = new URLSearchParams(params).toString();
  try {
    const reponse = await fetch(`${API_LIVRES}/livres${query ? "?" + query : ""}`);
    const livres = await reponse.json();
    livresCache = livres;

    document.getElementById("compteur-livres").textContent =
      `${livres.length} livre${livres.length > 1 ? "s" : ""}`;

    if (livres.length === 0) {
      tableauLivres.innerHTML = ligneEtatVide(6, "Aucun livre pour le moment.");
      return;
    }

    tableauLivres.innerHTML = livres
      .map(
        (livre) => `
        <tr>
          <td class="col-id">#${livre.id}</td>
          <td>${echapperHtml(livre.titre)}</td>
          <td>${echapperHtml(livre.auteur)}</td>
          <td>${echapperHtml(livre.isbn)}</td>
          <td>
            <span class="badge ${livre.disponible ? "badge-succes" : "badge-danger"}">
              ${livre.disponible ? "Disponible" : "Emprunté"}
            </span>
          </td>
          <td class="cellule-actions">
            <button class="btn btn-petit btn-fantome" data-action="editer" data-id="${livre.id}">Éditer</button>
            <button class="btn btn-petit btn-danger" data-action="supprimer" data-id="${livre.id}">Supprimer</button>
          </td>
        </tr>`
      )
      .join("");
  } catch (erreur) {
    afficherMessage("message-livres", "Impossible de contacter le service Livres.", "erreur");
  }
}

tableauLivres.addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button[data-action]");
  if (!bouton) return;

  const id = parseInt(bouton.dataset.id, 10);
  if (bouton.dataset.action === "editer") {
    const livre = livresCache.find((l) => l.id === id);
    if (livre) modifierLivreFormulaire(livre.id, livre.titre, livre.auteur, livre.isbn);
  } else if (bouton.dataset.action === "supprimer") {
    supprimerLivre(id);
  }
});

formLivre.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();

  const id = document.getElementById("livre-id").value;
  const corps = {
    titre: document.getElementById("livre-titre").value,
    auteur: document.getElementById("livre-auteur").value,
    isbn: document.getElementById("livre-isbn").value,
  };

  definirChargement(boutonLivreSubmit, true, "Envoi...", id ? "Modifier le livre" : "Ajouter le livre");
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
    boutonLivreSubmit.textContent = "Ajouter le livre";
    chargerLivres();
  } catch (erreur) {
    afficherMessage("message-livres", erreur.message, "erreur");
  } finally {
    definirChargement(boutonLivreSubmit, false, "", document.getElementById("livre-id").value ? "Modifier le livre" : "Ajouter le livre");
  }
});

document.getElementById("livre-annuler").addEventListener("click", () => {
  formLivre.reset();
  document.getElementById("livre-id").value = "";
  boutonLivreSubmit.textContent = "Ajouter le livre";
});

function modifierLivreFormulaire(id, titre, auteur, isbn) {
  document.getElementById("livre-id").value = id;
  document.getElementById("livre-titre").value = titre;
  document.getElementById("livre-auteur").value = auteur;
  document.getElementById("livre-isbn").value = isbn;
  boutonLivreSubmit.textContent = "Modifier le livre";
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
const boutonUtilisateurSubmit = document.getElementById("utilisateur-submit");

async function chargerUtilisateurs() {
  try {
    const reponse = await fetch(`${API_UTILISATEURS}/utilisateurs`);
    const utilisateurs = await reponse.json();
    utilisateursCache = utilisateurs;

    document.getElementById("compteur-utilisateurs").textContent =
      `${utilisateurs.length} utilisateur${utilisateurs.length > 1 ? "s" : ""}`;

    if (utilisateurs.length === 0) {
      tableauUtilisateurs.innerHTML = ligneEtatVide(4, "Aucun utilisateur pour le moment.");
      return;
    }

    tableauUtilisateurs.innerHTML = utilisateurs
      .map(
        (u) => `
        <tr>
          <td class="col-id">#${u.id}</td>
          <td>${echapperHtml(u.nom)}</td>
          <td>${echapperHtml(u.email)}</td>
          <td>${echapperHtml(u.type)}</td>
        </tr>`
      )
      .join("");
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

  definirChargement(boutonUtilisateurSubmit, true, "Envoi...", "Créer l'utilisateur");
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
  } finally {
    definirChargement(boutonUtilisateurSubmit, false, "", "Créer l'utilisateur");
  }
});

// ============================================================
// SECTION EMPRUNTS
// ============================================================
const formEmprunt = document.getElementById("form-emprunt");
const tableauEmprunts = document.getElementById("tableau-emprunts");
const boutonEmpruntSubmit = document.getElementById("emprunt-submit");

function nomLivre(id) {
  const livre = livresCache.find((l) => l.id === id);
  return livre ? echapperHtml(livre.titre) : `Livre #${id}`;
}

function nomUtilisateur(id) {
  const utilisateur = utilisateursCache.find((u) => u.id === id);
  return utilisateur ? echapperHtml(utilisateur.nom) : `Utilisateur #${id}`;
}

async function chargerEmprunts() {
  try {
    const reponse = await fetch(`${API_EMPRUNTS}/emprunts`);
    const emprunts = await reponse.json();

    document.getElementById("compteur-emprunts").textContent =
      `${emprunts.length} emprunt${emprunts.length > 1 ? "s" : ""}`;

    if (emprunts.length === 0) {
      tableauEmprunts.innerHTML = ligneEtatVide(5, "Aucun emprunt enregistré pour le moment.");
      return;
    }

    tableauEmprunts.innerHTML = emprunts
      .map((e) => {
        const dejaRetourne = e.date_retour !== null;
        return `
        <tr>
          <td>${nomLivre(e.id_livre)}</td>
          <td>${nomUtilisateur(e.id_utilisateur)}</td>
          <td>${new Date(e.date_emprunt).toLocaleString("fr-FR")}</td>
          <td>${dejaRetourne ? new Date(e.date_retour).toLocaleString("fr-FR") : "—"}</td>
          <td class="cellule-actions">
            ${
              dejaRetourne
                ? '<span class="badge badge-succes">Retourné</span>'
                : `<button class="btn btn-petit btn-secondaire" data-action="retour" data-id="${e.id}">Marquer retourné</button>`
            }
          </td>
        </tr>`;
      })
      .join("");
  } catch (erreur) {
    afficherMessage("message-emprunts", "Impossible de contacter le service Emprunts.", "erreur");
  }
}

tableauEmprunts.addEventListener("click", (evenement) => {
  const bouton = evenement.target.closest("button[data-action='retour']");
  if (!bouton) return;
  retournerLivre(parseInt(bouton.dataset.id, 10));
});

formEmprunt.addEventListener("submit", async (evenement) => {
  evenement.preventDefault();

  const corps = {
    id_livre: parseInt(document.getElementById("emprunt-id-livre").value, 10),
    id_utilisateur: parseInt(document.getElementById("emprunt-id-utilisateur").value, 10),
  };

  definirChargement(boutonEmpruntSubmit, true, "Envoi...", "Emprunter");
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
    await chargerLivres(); // Le livre passe indisponible, on rafraîchit le cache et la liste
    chargerEmprunts();
  } catch (erreur) {
    afficherMessage("message-emprunts", erreur.message, "erreur");
  } finally {
    definirChargement(boutonEmpruntSubmit, false, "", "Emprunter");
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
    await chargerLivres(); // Le livre redevient disponible, on rafraîchit le cache et la liste
    chargerEmprunts();
  } catch (erreur) {
    afficherMessage("message-emprunts", erreur.message, "erreur");
  }
}

// ============================================================
// Chargement initial des données au démarrage de la page
// ============================================================
(async function initialiser() {
  await Promise.all([chargerLivres(), chargerUtilisateurs()]);
  chargerEmprunts();
})();
