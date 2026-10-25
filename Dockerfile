# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.14 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend

ARG INSTALL_JARVIS=false
RUN if [ "$INSTALL_JARVIS" = "true" ]; then \
        uv sync --frozen --no-dev --extra jarvis; \
    else \
        uv sync --frozen --no-dev; \
    fi

COPY alembic.ini ./
COPY alembic ./alembic
COPY simulator_assumptions.yaml ./

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 10001 wattson \
    && mkdir -p /app/.data \
    && chown -R wattson:wattson /app/.data

USER wattson

EXPOSE 8000

CMD ["uvicorn", "wattson.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
