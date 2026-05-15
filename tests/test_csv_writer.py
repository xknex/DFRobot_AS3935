"""Unit tests for the CsvWriter component."""

import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lightning_collector.csv_writer import CSV_COLUMNS, CsvWriter
from lightning_common.models import EventRecord, EventType


@pytest.fixture
def csv_path(tmp_path: Path) -> str:
    """Return a temporary CSV file path."""
    return str(tmp_path / "events.csv")


class TestCsvWriterInit:
    """Tests for CsvWriter initialization."""

    def test_creates_file_with_header(self, csv_path: str) -> None:
        """New file gets a header row on creation."""
        writer = CsvWriter(csv_path)
        writer.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        assert header == CSV_COLUMNS

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created if they don't exist."""
        nested_path = str(tmp_path / "sub" / "dir" / "events.csv")
        writer = CsvWriter(nested_path)
        writer.close()

        assert Path(nested_path).exists()

    def test_does_not_duplicate_header_on_reopen(self, csv_path: str) -> None:
        """Reopening an existing file does not write a second header."""
        writer = CsvWriter(csv_path)
        writer.close()

        writer2 = CsvWriter(csv_path)
        writer2.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # Only one header row
        assert len(rows) == 1
        assert rows[0] == CSV_COLUMNS


class TestCsvWriterWrite:
    """Tests for CsvWriter.write()."""

    def test_writes_lightning_event(self, csv_path: str) -> None:
        """Lightning event is written with all fields populated."""
        record = EventRecord(
            timestamp=datetime(2024, 7, 15, 14, 32, 1, 123456, tzinfo=timezone.utc),
            event_type=EventType.LIGHTNING,
            distance_km=12,
            energy_normalized=0.45,
        )

        writer = CsvWriter(csv_path)
        writer.write(record)
        writer.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)

        assert row == [
            "2024-07-15T14:32:01.123456+00:00",
            "lightning",
            "12",
            "0.45",
        ]

    def test_writes_disturber_event_with_empty_fields(self, csv_path: str) -> None:
        """Disturber event has empty distance_km and energy_normalized."""
        record = EventRecord(
            timestamp=datetime(2024, 7, 15, 14, 32, 5, 789012, tzinfo=timezone.utc),
            event_type=EventType.DISTURBER,
        )

        writer = CsvWriter(csv_path)
        writer.write(record)
        writer.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)

        assert row == [
            "2024-07-15T14:32:05.789012+00:00",
            "disturber",
            "",
            "",
        ]

    def test_writes_noise_event_with_empty_fields(self, csv_path: str) -> None:
        """Noise event has empty distance_km and energy_normalized."""
        record = EventRecord(
            timestamp=datetime(2024, 7, 15, 14, 33, 0, 0, tzinfo=timezone.utc),
            event_type=EventType.NOISE,
        )

        writer = CsvWriter(csv_path)
        writer.write(record)
        writer.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            row = next(reader)

        assert row == [
            "2024-07-15T14:33:00+00:00",
            "noise",
            "",
            "",
        ]

    def test_multiple_writes_append(self, csv_path: str) -> None:
        """Multiple writes append rows without overwriting."""
        records = [
            EventRecord(
                timestamp=datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc),
                event_type=EventType.LIGHTNING,
                distance_km=5,
                energy_normalized=0.8,
            ),
            EventRecord(
                timestamp=datetime(2024, 7, 15, 14, 32, 2, tzinfo=timezone.utc),
                event_type=EventType.NOISE,
            ),
        ]

        writer = CsvWriter(csv_path)
        for r in records:
            writer.write(r)
        writer.close()

        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # header + 2 data rows
        assert len(rows) == 3

    def test_write_failure_does_not_raise(
        self, csv_path: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write failure is logged but does not propagate."""
        writer = CsvWriter(csv_path)

        # Force an error by closing the underlying file
        writer._file.close()

        record = EventRecord(
            timestamp=datetime(2024, 7, 15, 14, 32, 1, tzinfo=timezone.utc),
            event_type=EventType.NOISE,
        )

        # Should not raise
        writer.write(record)


class TestCsvWriterClose:
    """Tests for CsvWriter.close()."""

    def test_close_is_idempotent(self, csv_path: str) -> None:
        """Calling close multiple times does not raise."""
        writer = CsvWriter(csv_path)
        writer.close()
        writer.close()  # Should not raise
