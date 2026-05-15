"""FastAPI application factory for the Lightning REST API."""

from __future__ import annotations

import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import mariadb
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lightning_common.config import ApiSettings

logger = logging.getLogger(__name__)

# Module-level reference to the connection pool for dependency injection
_pool: mariadb.ConnectionPool | None = None
_start_time: float = 0.0


def get_pool() -> mariadb.ConnectionPool | None:
    """Return the current connection pool instance."""
    return _pool


def get_start_time() -> float:
    """Return the application start time (monotonic clock)."""
    return _start_time


def _mask_password(password: str) -> str:
    """Mask a password for safe logging."""
    if len(password) <= 2:
        return "***"
    return f"{password[0]}{'*' * (len(password) - 2)}{password[-1]}"


def _log_config(settings: ApiSettings) -> None:
    """Log configuration with masked credentials."""
    logger.info(
        "API Configuration: db_host=%s, db_port=%d, db_user=%s, "
        "db_password=%s, db_name=%s, api_host=%s, api_port=%d, "
        "cors_origins=%s, db_pool_size=%d",
        settings.db_host,
        settings.db_port,
        settings.db_user,
        _mask_password(settings.db_password),
        settings.db_name,
        settings.api_host,
        settings.api_port,
        settings.cors_origins,
        settings.db_pool_size,
    )


def _create_pool(settings: ApiSettings) -> mariadb.ConnectionPool:
    """Create a MariaDB connection pool from settings."""
    pool = mariadb.ConnectionPool(
        pool_name="lightning_api_pool",
        pool_size=settings.db_pool_size,
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    return pool


def _confirm_db_connectivity(pool: mariadb.ConnectionPool) -> None:
    """Confirm database connectivity by acquiring and releasing a connection."""
    conn = pool.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        logger.info("Database connectivity confirmed")
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: create DB pool on startup, close on shutdown."""
    global _pool, _start_time

    settings: ApiSettings = app.state.settings
    _start_time = time.monotonic()

    # Log configuration with masked credentials
    _log_config(settings)

    # Create connection pool and confirm connectivity
    try:
        _pool = _create_pool(settings)
        _confirm_db_connectivity(_pool)
    except mariadb.Error:
        logger.exception("Failed to create database connection pool")
        raise

    yield

    # Shutdown: close the pool
    if _pool is not None:
        try:
            _pool.close()
            logger.info("Database connection pool closed")
        except Exception:
            logger.exception("Error closing database connection pool")
        _pool = None


def _handle_sigterm(signum: int, frame: object) -> None:
    """Handle SIGTERM: close DB pool and exit cleanly within 5s."""
    global _pool
    logger.info("Received SIGTERM, shutting down gracefully")

    if _pool is not None:
        try:
            _pool.close()
            logger.info("Database connection pool closed on SIGTERM")
        except Exception:
            logger.exception("Error closing pool during SIGTERM shutdown")
        _pool = None

    sys.exit(0)


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    settings : ApiSettings | None
        Application settings. If None, settings are loaded from
        environment variables / TOML file.

    Returns
    -------
    FastAPI
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = ApiSettings()

    app = FastAPI(
        title="Lightning Data Pipeline API",
        description="REST API for lightning event data from the AS3935 sensor",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Store settings on app state for access in lifespan and routes
    app.state.settings = settings

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register SIGTERM handler
    signal.signal(signal.SIGTERM, _handle_sigterm)

    # Register route modules
    from lightning_api.routes.events import router as events_router
    from lightning_api.routes.health import router as health_router

    app.include_router(events_router)
    app.include_router(health_router)

    return app
