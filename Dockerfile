# POLYBOT - Immagine per esecuzione 24/7
FROM python:3.11-slim

WORKDIR /app

# Dipendenze di sistema (opzionali, per eventuali lib native)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Il .env va fornito a runtime (env_file in docker-compose o -e)
CMD ["python3", "bot_async.py"]
