"""Dependency injection for the Lightning REST API."""

from __future__ import annotations

from typing import Generator

import mariadb
from fastapi import HTTPException

from lightning_api.app import get_pool


def get_db_connection() -> Generator[mariadb.Connection, None, None]:
    """FastAPI dependency that yields a connection from the pool.

    Acquires a connection from the MariaDB connection pool, yields it
    for use in the request handler, and returns it to the pool after use.

    Yields
    ------
    mariadb.Connection
        An active database connection from the pool.

    Raises
    ------
    HTTPException
        503 if the database pool is unavailable or exhausted.
    """
    pool = get_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        conn = pool.get_connection()
    except mariadb.PoolError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        yield conn
    finally:
        conn.close()
