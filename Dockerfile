# =============================================================================
# Lightning Data Pipeline — Production Dockerfile
# =============================================================================
# Multi-stage build for the Lightning REST API service.
#
# Key decisions:
# - python:3.11-slim as base (matches requires-python = ">=3.11", minimal image)
# - Multi-stage: build stage compiles the mariadb C extension, runtime is lean
# - Custom entrypoint handles first-deployment initialization:
#   • Validates all required env vars with clear error messages
#   • Waits for MariaDB with retries and diagnostic output
#   • Creates the database schema (events table + indexes)
#   • Then starts the API service
# - Non-root user for security
# - Only the API is containerized; the collector requires physical I2C/GPIO
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build — install system build deps and compile Python packages
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libmariadb-dev \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies into a virtual env so we can copy it cleanly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what pip needs first (layer caching)
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image with only runtime libraries
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmariadb3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash lightning

# Copy the pre-built virtual env from builder (packages are in site-packages)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the Docker entrypoint script
COPY docker/entrypoint.py /app/docker/entrypoint.py

WORKDIR /app

# Switch to non-root user
USER lightning

# Expose the API port (default 8000, configurable via LIGHTNING_API_PORT)
EXPOSE 8000

# Health check using the built-in /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${LIGHTNING_API_PORT:-8000}/health || exit 1

# Default: run the entrypoint in API mode (validates env, waits for DB, inits schema, starts API)
ENTRYPOINT ["python", "docker/entrypoint.py"]
CMD ["api"]
