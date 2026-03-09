FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos "" cinebot && \
    chown -R cinebot:cinebot /app

USER cinebot

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import asyncio; from bot.models.engine import redis_client; asyncio.run(redis_client.ping())" || exit 1

CMD ["python", "run.py"]