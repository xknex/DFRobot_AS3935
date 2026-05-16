# Feature: lightning-data-pipeline, Property 2: CSV serialization round-trip
# Feature: lightning-data-pipeline, Property 3: Write buffer preserves records in chronological order
# Feature: lightning-data-pipeline, Property 4: Write buffer bounded size invariant
"""Property-based tests for the Lightning Data Pipeline collector components.

This module contains Hypothesis property tests for CSV serialization
round-trip correctness, write buffer ordering, and write buffer bounded size invariant.

**Validates: Requirements 2.1, 2.2, 3.3, 3.5, 3.6**
"""

import csv
import uuid
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from lightning_collector.csv_writer import CSV_COLUMNS, CsvWriter
from lightning_collector.db_writer import DbWriter
from lightning_common.config import CollectorSettings
from lightning_common.models import EventRecord, EventType


# ===========================================================================
# Shared Strategies
# ===========================================================================

# Generate valid UTC timestamps
_utc_timestamps = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
    timezones=st.just(timezone.utc),
)

# Generate valid lightning EventRecords
_lightning_records = st.builds(
    EventRecord,
    timestamp=_utc_timestamps,
    event_type=st.just(EventType.LIGHTNING),
    distance_km=st.integers(min_value=0, max_value=63),
    energy_normalized=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
)

# Generate valid non-lightning EventRecords (disturber or noise)
_non_lightning_records = st.builds(
    EventRecord,
    timestamp=_utc_timestamps,
    event_type=st.sampled_from([EventType.DISTURBER, EventType.NOISE]),
    distance_km=st.none(),
    energy_normalized=st.none(),
)

# Generate any valid EventRecord
_valid_event_records = st.one_of(_lightning_records, _non_lightning_records)


# ===========================================================================
# Property 2: CSV serialization round-trip
# ===========================================================================


@pytest.mark.property
class TestProperty2CsvSerializationRoundTrip:
    """Property 2: CSV serialization round-trip.

    For any valid EventRecord, serializing it to a CSV row and parsing that
    row back SHALL produce an EventRecord with identical field values, and
    the CSV columns SHALL appear in the order: timestamp, event_type,
    distance_km, energy_normalized.

    **Validates: Requirements 2.1, 2.2**
    """

    @given(record=_valid_event_records)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_csv_round_trip_preserves_field_values(
        self, record: EventRecord, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Serializing to CSV and parsing back produces identical field values."""
        # Use a unique filename per example to avoid accumulation from fixture reuse
        csv_path = str(tmp_path / f"round_trip_{uuid.uuid4().hex}.csv")

        # Write the record
        writer = CsvWriter(csv_path)
        writer.write(record)
        writer.close()

        # Read back the CSV
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        row = rows[0]

        # Verify timestamp round-trip
        parsed_timestamp = datetime.fromisoformat(row["timestamp"])
        assert parsed_timestamp == record.timestamp

        # Verify event_type round-trip
        assert row["event_type"] == record.event_type.value

        # Verify distance_km round-trip
        if record.distance_km is not None:
            assert int(row["distance_km"]) == record.distance_km
        else:
            assert row["distance_km"] == ""

        # Verify energy_normalized round-trip
        if record.energy_normalized is not None:
            assert float(row["energy_normalized"]) == pytest.approx(
                record.energy_normalized
            )
        else:
            assert row["energy_normalized"] == ""

    @given(record=_valid_event_records)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_csv_columns_in_correct_order(
        self, record: EventRecord, tmp_path: pytest.TempPathFactory
    ) -> None:
        """CSV columns appear in the order defined by CSV_COLUMNS constant."""
        # Use a unique filename per example to avoid accumulation from fixture reuse
        csv_path = str(tmp_path / f"column_order_{uuid.uuid4().hex}.csv")

        writer = CsvWriter(csv_path)
        writer.write(record)
        writer.close()

        # Read back the raw CSV header
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        # Verify column order matches CSV_COLUMNS
        assert header == CSV_COLUMNS
        assert header == ["timestamp", "event_type", "distance_km", "energy_normalized"]



# ===========================================================================
# Property 4: Write buffer bounded size invariant
# ===========================================================================


@pytest.mark.property
class TestProperty4WriteBufferBoundedSize:
    """Property 4: Write buffer bounded size invariant.

    For any sequence of N EventRecords added to the write buffer (where
    N > 10000), the buffer size SHALL never exceed 10000, and the buffer
    SHALL contain only the most recent 10000 records.

    **Validates: Requirements 3.6**
    """

    @given(
        num_records=st.integers(min_value=10001, max_value=15000),
    )
    @settings(max_examples=100, deadline=None)
    @patch("lightning_collector.db_writer.get_connection")
    def test_buffer_never_exceeds_max_size(
        self, mock_get_conn, num_records: int
    ) -> None:
        """Buffer size never exceeds 10000 regardless of how many records are added."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        collector_settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=10000,
        )
        writer = DbWriter(collector_settings)

        for i in range(num_records):
            record = EventRecord(
                timestamp=datetime(2024, 1, 1, 0, 0, i % 60, tzinfo=timezone.utc),
                event_type=EventType.NOISE,
            )
            writer.write(record)
            # Invariant: buffer size never exceeds 10000 at any point
            assert writer.buffer_size <= 10000

        # Final check: buffer is exactly at max capacity
        assert writer.buffer_size == 10000

    @given(
        num_records=st.integers(min_value=10001, max_value=15000),
    )
    @settings(max_examples=100, deadline=None)
    @patch("lightning_collector.db_writer.get_connection")
    def test_buffer_contains_only_most_recent_records(
        self, mock_get_conn, num_records: int
    ) -> None:
        """Buffer contains only the most recent 10000 records after overflow."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        collector_settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=10000,
        )
        writer = DbWriter(collector_settings)

        # Create records with unique, sequential timestamps
        all_records = [
            EventRecord(
                timestamp=datetime(
                    2024, 1, 1 + (i // 86400), (i // 3600) % 24, (i // 60) % 60, i % 60,
                    tzinfo=timezone.utc,
                ),
                event_type=EventType.NOISE,
            )
            for i in range(num_records)
        ]

        for record in all_records:
            writer.write(record)

        # The buffer should contain exactly the last 10000 records
        expected_records = all_records[-10000:]
        buffer_contents = list(writer._buffer)

        assert len(buffer_contents) == 10000
        assert buffer_contents == expected_records



# ===========================================================================
# Property 3: Write buffer preserves records in chronological order
# ===========================================================================


@pytest.mark.property
class TestProperty3WriteBufferOrdering:
    """Property 3: Write buffer preserves records in chronological order.

    For any sequence of EventRecords written while the database is unavailable,
    flushing the write buffer SHALL yield all records in the same chronological
    order they were enqueued.

    **Validates: Requirements 3.3, 3.5**
    """

    @given(records=st.lists(_valid_event_records, min_size=1, max_size=50))
    @settings(max_examples=100, deadline=None)
    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_preserves_enqueue_order(
        self, mock_get_conn, records: list[EventRecord]
    ) -> None:
        """Flushing the buffer yields records in the same order they were enqueued."""
        import mariadb

        # Simulate DB unavailable during writes
        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=10000,
        )
        writer = DbWriter(settings)

        # Write all records while DB is unavailable
        for record in records:
            writer.write(record)

        assert writer.buffer_size == len(records)

        # Simulate reconnection
        mock_conn = type("MockConn", (), {
            "cursor": lambda self: type("MockCursor", (), {
                "execute": lambda self, *a, **kw: None,
                "close": lambda self: None,
            })(),
            "commit": lambda self: None,
            "close": lambda self: None,
        })()
        mock_get_conn.side_effect = None
        mock_get_conn.return_value = mock_conn

        writer.reconnect()

        # Capture the order of records flushed by inspecting the buffer directly
        # before flush - the deque preserves insertion order (FIFO)
        buffered_records = list(writer._buffer)

        # Verify buffer order matches enqueue order
        assert buffered_records == records

        # Now flush and verify all records are flushed
        flushed_count = writer.flush_buffer()
        assert flushed_count == len(records)
        assert writer.buffer_size == 0

    @given(records=st.lists(_valid_event_records, min_size=2, max_size=30))
    @settings(max_examples=100, deadline=None)
    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_inserts_in_enqueue_order(
        self, mock_get_conn, records: list[EventRecord]
    ) -> None:
        """Records are inserted into the database in the same order they were enqueued."""
        import mariadb

        # Simulate DB unavailable during writes
        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=10000,
        )
        writer = DbWriter(settings)

        # Write all records while DB is unavailable
        for record in records:
            writer.write(record)

        # Simulate reconnection with a mock that tracks insert order
        inserted_timestamps: list[datetime] = []

        class MockCursor:
            def execute(self, sql, params):
                inserted_timestamps.append(params[0])

            def close(self):
                pass

        class MockConn:
            def cursor(self):
                return MockCursor()

            def commit(self):
                pass

            def close(self):
                pass

        mock_get_conn.side_effect = None
        mock_get_conn.return_value = MockConn()

        writer.reconnect()
        flushed_count = writer.flush_buffer()

        # Verify all records were flushed
        assert flushed_count == len(records)

        # Verify insert order matches enqueue order
        expected_timestamps = [r.timestamp for r in records]
        assert inserted_timestamps == expected_timestamps
