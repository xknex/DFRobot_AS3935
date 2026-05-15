"""CSV persistence component for the Lightning Collector Service.

Appends EventRecord instances to a local CSV file with immediate flush
to prevent data loss on unexpected shutdown.
"""

import csv
import logging
import os
from pathlib import Path

from lightning_common.models import EventRecord

logger = logging.getLogger(__name__)

CSV_COLUMNS = ["timestamp", "event_type", "distance_km", "energy_normalized"]


class CsvWriter:
    """Writes EventRecord instances to a CSV file.

    Creates the file with a header row if it does not exist.
    Flushes each write to disk immediately. Logs and continues
    on write failure without re-raising exceptions.
    """

    def __init__(self, file_path: str) -> None:
        """Initialize the CSV writer.

        Args:
            file_path: Path to the CSV file. Parent directories are created
                       if they do not exist.
        """
        self._file_path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        file_exists = self._file_path.exists() and self._file_path.stat().st_size > 0

        self._file = open(self._file_path, mode="a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)

        if not file_exists:
            self._writer.writerow(CSV_COLUMNS)
            self._file.flush()
            os.fsync(self._file.fileno())
            logger.info("Created CSV file with header: %s", self._file_path)

    def write(self, record: EventRecord) -> None:
        """Append an EventRecord as a single CSV row.

        For non-lightning events, distance_km and energy_normalized are
        written as empty strings. Flushes to disk after each write.

        Args:
            record: The event record to persist.
        """
        try:
            row = [
                record.timestamp.isoformat(),
                record.event_type.value,
                record.distance_km if record.distance_km is not None else "",
                record.energy_normalized if record.energy_normalized is not None else "",
            ]
            self._writer.writerow(row)
            self._file.flush()
            os.fsync(self._file.fileno())
        except Exception:
            logger.exception("Failed to write record to CSV: %s", self._file_path)

    def close(self) -> None:
        """Close the underlying file handle."""
        try:
            self._file.close()
        except Exception:
            logger.exception("Failed to close CSV file: %s", self._file_path)
