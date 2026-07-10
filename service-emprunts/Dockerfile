# Image Python légère
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Le service Emprunts écoute sur le port 5003
EXPOSE 5003

CMD ["python", "app.py"]
