# Image Python légère
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Le backend écoute sur le port 5001
EXPOSE 5001

CMD ["python", "app.py"]
