# Veriprops backend image — FastAPI (Python 3.12) served by gunicorn/uvicorn.
# Multi-stage: builder compiles deps into a venv -> slim runtime carries only the
# venv (no compiler toolchain) + curl for the healthcheck.

# --- builder: compile dependencies into an isolated venv ----------------------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Build toolchain for any packages without a matching wheel (argon2, asyncpg, …).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

# Install into the venv first so the layer caches across source changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# --- runtime: lean image with just the venv + app source ----------------------
FROM python:3.12-slim AS runtime

# Faster, quieter Python in containers; run against the prebuilt venv.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# curl is kept only for the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Prebuilt dependencies (no compiler toolchain trails into the final image).
COPY --from=builder /opt/venv /opt/venv

# Application source (env files are excluded via .dockerignore — settings are
# supplied through the container environment / compose env_file at runtime).
COPY . .

# Run as an unprivileged user.
RUN useradd --create-home --uid 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# `APPODUS_ACTIVE_ENV` selects the .env.{env}; compose sets it and the DB/SMTP/Redis
# hosts. Alembic migrations are run by the compose command before the server starts.
CMD ["gunicorn", "veriprops:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "300"]
