FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/justinsimonelli/docker-log-alerter

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY alerter/ ./alerter/

# Note: Runs as root to access Docker socket (same as Watchtower, Traefik, etc.)
CMD ["python", "-m", "alerter.main"]
