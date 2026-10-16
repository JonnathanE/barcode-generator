# syntax=docker/dockerfile:1

# ---------- builder: resuelve dependencias con uv a partir del lockfile ----------
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------- base: imagen final con Ghostscript y usuario no root ----------
FROM python:3.14-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app

# ---------- dev: dependencias de desarrollo + recarga (docker compose) ----------
FROM base AS dev
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project && chown -R app:app /opt/venv
USER app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --reload"]

# ---------- runtime: imagen de producción (Render) ----------
FROM base AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
USER app
EXPOSE 8000
# Render inyecta $PORT; forma shell para expandir la variable.
# --proxy-headers: la IP del cliente sale de X-Forwarded-For (proxy de Render), necesario
# para el rate limiting por IP. Seguro porque el contenedor solo recibe tráfico del proxy.
ENV FORWARDED_ALLOW_IPS="*"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --no-access-log"]
