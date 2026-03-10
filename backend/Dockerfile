# ── Stage 1: install dependencies ──────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Build tools — safety net for packages without pre-built wheels
# on some platforms. Discarded in final stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy everything setuptools needs: metadata + package source
COPY pyproject.toml ./
COPY app/ ./app/

# Install production deps only (no dev extras)
RUN pip install --no-cache-dir .

# ── Stage 2: runtime image ────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copy installed Python packages and CLI entrypoints from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY app/ ./app/
# Alembic config + migrations (migrations run from same image per aws-deployment.md)
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/

# Non-root user for runtime
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

EXPOSE 8000

# Default: web server. Override command at runtime for worker or migrations.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
