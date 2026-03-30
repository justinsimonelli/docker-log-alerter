FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/justinsimonelli/docker-log-alerter

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY alerter/ ./alerter/

# Run as non-root user
RUN useradd -m alerter
USER alerter

CMD ["python", "-m", "alerter.main"]
