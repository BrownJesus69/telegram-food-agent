# syntax=docker/dockerfile:1
FROM python:3.12-slim

ARG GIT_SHA=dev
LABEL org.opencontainers.image.title="foodbot" \
      org.opencontainers.image.description="Telegram food-ordering agent for Bengaluru (synthetic catalogue)" \
      org.opencontainers.image.revision=$GIT_SHA

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# dependencies first so code changes don't invalidate this layer
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY foodbot ./foodbot
COPY seed_data ./seed_data
COPY evals/RESULTS.md ./evals/RESULTS.md

# unprivileged user; /data holds the SQLite database and backups (mounted as a volume)
RUN useradd --create-home --uid 10001 bot && mkdir -p /data/backups && chown -R bot /data
USER bot

ENV DB_PATH=/data/foodbot.db \
    BACKUP_DIR=/data/backups \
    OPS_HOST=0.0.0.0 \
    OPS_PORT=8080 \
    LOG_FORMAT=json

VOLUME /data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-m", "foodbot.healthcheck"]

CMD ["python", "-m", "foodbot"]
