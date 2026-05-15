"""Shared data models for the Lightning Data Pipeline."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, model_validator


class EventType(StrEnum):
    """Type of event detected by the AS3935 sensor."""

    LIGHTNING = "lightning"
    DISTURBER = "disturber"
    NOISE = "noise"


class EventRecord(BaseModel):
    """A single timestamped event detected by the AS3935 sensor.

    For lightning events, distance_km and energy_normalized are populated.
    For disturber and noise events, both fields must be None.
    """

    timestamp: datetime
    event_type: EventType
    distance_km: int | None = None
    energy_normalized: float | None = None

    @model_validator(mode="after")
    def validate_non_lightning_fields(self) -> "EventRecord":
        """Ensure distance_km and energy_normalized are None for non-lightning events."""
        if self.event_type != EventType.LIGHTNING:
            if self.distance_km is not None:
                raise ValueError(
                    "distance_km must be None for non-lightning events"
                )
            if self.energy_normalized is not None:
                raise ValueError(
                    "energy_normalized must be None for non-lightning events"
                )
        return self
