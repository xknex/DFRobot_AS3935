"""Pydantic response models for the Lightning REST API."""

from datetime import datetime

from pydantic import BaseModel

from lightning_common.models import EventType


class EventResponse(BaseModel):
    """Response model for a single lightning event."""

    id: int
    timestamp: datetime
    event_type: EventType
    distance_km: int | None = None
    energy_normalized: float | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated responses."""

    total_count: int
    page: int
    page_size: int
    total_pages: int


class PaginatedEventsResponse(BaseModel):
    """Response model for paginated event listings."""

    data: list[EventResponse]
    pagination: PaginationMeta


class StatsResponse(BaseModel):
    """Response model for event statistics."""

    count_by_type: dict[str, int]
    count_last_24h: int
    count_last_7d: int
    latest_event_timestamp: datetime | None = None


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str
    database: str
    uptime_seconds: float
