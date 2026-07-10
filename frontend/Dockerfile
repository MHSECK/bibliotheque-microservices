# Image Nginx légère pour servir les fichiers statiques
FROM nginx:alpine

# Suppression de la configuration par défaut et copie des fichiers du site
COPY index.html /usr/share/nginx/html/index.html
COPY style.css /usr/share/nginx/html/style.css
COPY script.js /usr/share/nginx/html/script.js

# Nginx écoute par défaut sur le port 80 ; on le mappera sur 8080 côté hôte
EXPOSE 80
