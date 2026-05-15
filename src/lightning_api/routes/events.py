"""Event routes for the Lightning REST API.

Provides endpoints for listing, filtering, and retrieving lightning events,
as well as summary statistics.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import mariadb
from fastapi import APIRouter, Depends, HTTPException, Query

from lightning_api.dependencies import get_db_connection
from lightning_api.models import (
    EventResponse,
    PaginatedEventsResponse,
    PaginationMeta,
    StatsResponse,
)
from lightning_common.models import EventType

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PaginatedEventsResponse)
def list_events(
    page: int = Query(default=1, description="Page number (1-based)"),
    page_size: int = Query(default=50, description="Number of items per page"),
    start_date: datetime | None = Query(default=None, description="Filter: start date (ISO 8601)"),
    end_date: datetime | None = Query(default=None, description="Filter: end date (ISO 8601)"),
    event_type: EventType | None = Query(default=None, description="Filter: event type"),
    conn: mariadb.Connection = Depends(get_db_connection),
) -> PaginatedEventsResponse:
    """Return a paginated list of events with optional filters."""
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be at least 1")
    if page_size > 200:
        raise HTTPException(status_code=422, detail="page_size must not exceed 200")

    # Build WHERE clause dynamically
    conditions: list[str] = []
    params: list[object] = []

    if start_date is not None:
        conditions.append("timestamp >= ?")
        params.append(start_date)
    if end_date is not None:
        conditions.append("timestamp <= ?")
        params.append(end_date)
    if event_type is not None:
        conditions.append("event_type = ?")
        params.append(event_type.value)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    cursor = conn.cursor()
    try:
        # Get total count
        count_query = f"SELECT COUNT(*) FROM events {where_clause}"
        cursor.execute(count_query, tuple(params))
        row = cursor.fetchone()
        total_count: int = row[0] if row else 0

        # Calculate pagination
        total_pages = max(1, math.ceil(total_count / page_size))
        offset = (page - 1) * page_size

        # Fetch page of results
        data_query = (
            f"SELECT id, timestamp, event_type, distance_km, energy_normalized "
            f"FROM events {where_clause} "
            f"ORDER BY timestamp DESC "
            f"LIMIT ? OFFSET ?"
        )
        cursor.execute(data_query, tuple(params) + (page_size, offset))
        rows = cursor.fetchall()

        events = [
            EventResponse(
                id=r[0],
                timestamp=r[1],
                event_type=r[2],
                distance_km=r[3],
                energy_normalized=r[4],
            )
            for r in rows
        ]

        pagination = PaginationMeta(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

        return PaginatedEventsResponse(data=events, pagination=pagination)
    finally:
        cursor.close()


@router.get("/latest", response_model=EventResponse)
def get_latest_event(
    conn: mariadb.Connection = Depends(get_db_connection),
) -> EventResponse:
    """Return the most recent event."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, timestamp, event_type, distance_km, energy_normalized "
            "FROM events ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No events found")

        return EventResponse(
            id=row[0],
            timestamp=row[1],
            event_type=row[2],
            distance_km=row[3],
            energy_normalized=row[4],
        )
    finally:
        cursor.close()


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    conn: mariadb.Connection = Depends(get_db_connection),
) -> StatsResponse:
    """Return summary statistics about events."""
    cursor = conn.cursor()
    try:
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        # Count by type
        cursor.execute(
            "SELECT event_type, COUNT(*) FROM events GROUP BY event_type"
        )
        type_rows = cursor.fetchall()
        count_by_type: dict[str, int] = {
            "lightning": 0,
            "disturber": 0,
            "noise": 0,
        }
        for row in type_rows:
            count_by_type[row[0]] = row[1]

        # Count last 24h
        cursor.execute(
            "SELECT COUNT(*) FROM events WHERE timestamp >= ?",
            (last_24h,),
        )
        row = cursor.fetchone()
        count_last_24h: int = row[0] if row else 0

        # Count last 7d
        cursor.execute(
            "SELECT COUNT(*) FROM events WHERE timestamp >= ?",
            (last_7d,),
        )
        row = cursor.fetchone()
        count_last_7d: int = row[0] if row else 0

        # Latest event timestamp
        cursor.execute("SELECT MAX(timestamp) FROM events")
        row = cursor.fetchone()
        latest_event_timestamp: datetime | None = row[0] if row else None

        return StatsResponse(
            count_by_type=count_by_type,
            count_last_24h=count_last_24h,
            count_last_7d=count_last_7d,
            latest_event_timestamp=latest_event_timestamp,
        )
    finally:
        cursor.close()
