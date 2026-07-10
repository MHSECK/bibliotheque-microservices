# Image Python légère
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Le service Utilisateurs écoute sur le port 5002
EXPOSE 5002

CMD ["python", "app.py"]
