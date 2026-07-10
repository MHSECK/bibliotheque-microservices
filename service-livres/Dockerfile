# Image Python légère
FROM python:3.12-slim

# Répertoire de travail dans le conteneur
WORKDIR /app

# Installation des dépendances (mise en cache par Docker si requirements.txt ne change pas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code de l'application
COPY app.py .

# Le service Livres écoute sur le port 5001
EXPOSE 5001

# Lancement de l'application Flask
CMD ["python", "app.py"]
