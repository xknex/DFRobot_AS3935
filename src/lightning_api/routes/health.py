"""Health check route for the Lightning REST API."""

from __future__ import annotations

import logging
import time

import mariadb
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from lightning_api.app import get_pool, get_start_time
from lightning_api.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> JSONResponse:
    """Check service health including database connectivity.

    Returns HTTP 200 with status "healthy" when the database is reachable,
    or HTTP 503 with status "degraded" and an error description when it is not.
    """
    uptime = time.monotonic() - get_start_time()

    pool = get_pool()
    if pool is None:
        response = HealthResponse(
            status="degraded",
            database="error: connection pool not initialized",
            uptime_seconds=uptime,
        )
        return JSONResponse(content=response.model_dump(), status_code=503)

    try:
        conn = pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
        finally:
            conn.close()
    except mariadb.Error as exc:
        response = HealthResponse(
            status="degraded",
            database=f"error: {exc}",
            uptime_seconds=uptime,
        )
        return JSONResponse(content=response.model_dump(), status_code=503)

    response = HealthResponse(
        status="healthy",
        database="connected",
        uptime_seconds=uptime,
    )
    return JSONResponse(content=response.model_dump(), status_code=200)
