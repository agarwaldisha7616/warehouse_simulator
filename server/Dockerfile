# Dockerfile
# └─ Build context = project ROOT (run: docker build -f server/Dockerfile .)
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first (from project root) — better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project root into /app
# This ensures models.py, client.py, server/, openenv.yaml all land in /app
COPY . .

EXPOSE 7860

# uvicorn finds server/app.py as module server.app — correct because WORKDIR=/app
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
