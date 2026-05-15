"""Unit tests for the DbWriter component."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lightning_collector.db_writer import DbWriter
from lightning_common.config import CollectorSettings
from lightning_common.models import EventRecord, EventType


@pytest.fixture
def settings() -> CollectorSettings:
    """Return a CollectorSettings instance for testing."""
    return CollectorSettings(
        db_host="localhost",
        db_port=3306,
        db_user="test",
        db_password="secret",
        db_name="testdb",
        buffer_max_size=10000,
    )


@pytest.fixture
def lightning_record() -> EventRecord:
    """Return a sample lightning EventRecord."""
    return EventRecord(
        timestamp=datetime(2024, 7, 15, 14, 32, 1, 123456, tzinfo=timezone.utc),
        event_type=EventType.LIGHTNING,
        distance_km=12,
        energy_normalized=0.45,
    )


@pytest.fixture
def noise_record() -> EventRecord:
    """Return a sample noise EventRecord."""
    return EventRecord(
        timestamp=datetime(2024, 7, 15, 14, 33, 0, 0, tzinfo=timezone.utc),
        event_type=EventType.NOISE,
    )


class TestDbWriterInit:
    """Tests for DbWriter initialization."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_successful_connection(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """DbWriter connects on init when MariaDB is available."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        writer = DbWriter(settings)

        assert writer.is_connected is True
        assert writer.buffer_size == 0
        mock_get_conn.assert_called_once_with(
            host="localhost",
            port=3306,
            user="test",
            password="secret",
            database="testdb",
        )

    @patch("lightning_collector.db_writer.get_connection")
    def test_failed_connection_buffers(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """DbWriter starts in disconnected state when MariaDB is unavailable."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        writer = DbWriter(settings)

        assert writer.is_connected is False
        assert writer.buffer_size == 0


class TestDbWriterWrite:
    """Tests for DbWriter.write()."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_write_inserts_when_connected(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
        lightning_record: EventRecord,
    ) -> None:
        """write() inserts directly when connected."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        writer = DbWriter(settings)
        writer.write(lightning_record)

        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args
        assert "INSERT INTO events" in args[0][0]
        assert args[0][1] == (
            lightning_record.timestamp,
            "lightning",
            12,
            0.45,
        )
        mock_conn.commit.assert_called_once()
        assert writer.buffer_size == 0

    @patch("lightning_collector.db_writer.get_connection")
    def test_write_buffers_when_disconnected(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
        lightning_record: EventRecord,
    ) -> None:
        """write() buffers the record when not connected."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        writer = DbWriter(settings)
        writer.write(lightning_record)

        assert writer.buffer_size == 1

    @patch("lightning_collector.db_writer.get_connection")
    def test_write_buffers_on_insert_failure(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
        lightning_record: EventRecord,
    ) -> None:
        """write() buffers the record and marks connection lost on insert failure."""
        import mariadb

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = mariadb.Error("Insert failed")
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        writer = DbWriter(settings)
        assert writer.is_connected is True

        writer.write(lightning_record)

        assert writer.is_connected is False
        assert writer.buffer_size == 1

    @patch("lightning_collector.db_writer.get_connection")
    def test_write_uses_parameterized_query(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
        noise_record: EventRecord,
    ) -> None:
        """write() uses ? placeholders for parameterized queries."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        writer = DbWriter(settings)
        writer.write(noise_record)

        sql = mock_cursor.execute.call_args[0][0]
        assert "?" in sql
        assert "VALUES (?, ?, ?, ?)" in sql


class TestDbWriterFlushBuffer:
    """Tests for DbWriter.flush_buffer()."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_returns_zero_when_empty(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """flush_buffer() returns 0 when buffer is empty."""
        mock_get_conn.return_value = MagicMock()

        writer = DbWriter(settings)
        result = writer.flush_buffer()

        assert result == 0

    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_returns_zero_when_disconnected(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
        lightning_record: EventRecord,
    ) -> None:
        """flush_buffer() returns 0 when not connected."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        writer = DbWriter(settings)
        writer.write(lightning_record)
        result = writer.flush_buffer()

        assert result == 0
        assert writer.buffer_size == 1

    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_inserts_all_buffered_records(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
    ) -> None:
        """flush_buffer() inserts all buffered records and returns count."""
        import mariadb

        # Start disconnected
        mock_get_conn.side_effect = mariadb.Error("Connection refused")
        writer = DbWriter(settings)

        # Buffer some records
        records = [
            EventRecord(
                timestamp=datetime(2024, 7, 15, 14, 32, i, tzinfo=timezone.utc),
                event_type=EventType.NOISE,
            )
            for i in range(5)
        ]
        for r in records:
            writer.write(r)

        assert writer.buffer_size == 5

        # Simulate reconnection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.side_effect = None
        mock_get_conn.return_value = mock_conn

        writer.reconnect()
        result = writer.flush_buffer()

        assert result == 5
        assert writer.buffer_size == 0

    @patch("lightning_collector.db_writer.get_connection")
    def test_flush_preserves_chronological_order(
        self,
        mock_get_conn: MagicMock,
        settings: CollectorSettings,
    ) -> None:
        """flush_buffer() flushes records in the order they were enqueued."""
        import mariadb

        # Start disconnected
        mock_get_conn.side_effect = mariadb.Error("Connection refused")
        writer = DbWriter(settings)

        # Buffer records with distinct timestamps
        records = [
            EventRecord(
                timestamp=datetime(2024, 7, 15, 14, 32, i, tzinfo=timezone.utc),
                event_type=EventType.NOISE,
            )
            for i in range(3)
        ]
        for r in records:
            writer.write(r)

        # Reconnect
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.side_effect = None
        mock_get_conn.return_value = mock_conn

        writer.reconnect()
        writer.flush_buffer()

        # Verify insert order matches enqueue order
        calls = mock_cursor.execute.call_args_list
        timestamps = [call[0][1][0] for call in calls]
        assert timestamps == [r.timestamp for r in records]


class TestDbWriterReconnect:
    """Tests for DbWriter.reconnect()."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_reconnect_success(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """reconnect() returns True on successful reconnection."""
        import mariadb

        # Start disconnected
        mock_get_conn.side_effect = mariadb.Error("Connection refused")
        writer = DbWriter(settings)
        assert writer.is_connected is False

        # Reconnect succeeds
        mock_get_conn.side_effect = None
        mock_get_conn.return_value = MagicMock()

        result = writer.reconnect()

        assert result is True
        assert writer.is_connected is True

    @patch("lightning_collector.db_writer.get_connection")
    def test_reconnect_failure(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """reconnect() returns False on failed reconnection."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        writer = DbWriter(settings)
        result = writer.reconnect()

        assert result is False
        assert writer.is_connected is False


class TestDbWriterBufferFull:
    """Tests for buffer overflow behavior."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_buffer_discards_oldest_when_full(
        self, mock_get_conn: MagicMock
    ) -> None:
        """When buffer is full, oldest record is discarded on new append."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        # Use a small buffer for testing
        settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=3,
        )
        writer = DbWriter(settings)

        # Fill the buffer
        records = [
            EventRecord(
                timestamp=datetime(2024, 7, 15, 14, 32, i, tzinfo=timezone.utc),
                event_type=EventType.NOISE,
            )
            for i in range(4)
        ]
        for r in records:
            writer.write(r)

        # Buffer should contain only the 3 most recent
        assert writer.buffer_size == 3

    @patch("lightning_collector.db_writer.get_connection")
    def test_buffer_logs_warning_when_full(
        self, mock_get_conn: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A warning is logged when the buffer is full and a record is about to be discarded."""
        import logging

        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        settings = CollectorSettings(
            db_host="localhost",
            db_port=3306,
            db_user="test",
            db_password="secret",
            db_name="testdb",
            buffer_max_size=2,
        )
        writer = DbWriter(settings)

        # Fill the buffer
        for i in range(2):
            writer.write(
                EventRecord(
                    timestamp=datetime(2024, 7, 15, 14, 32, i, tzinfo=timezone.utc),
                    event_type=EventType.NOISE,
                )
            )

        # Next write should trigger warning
        with caplog.at_level(logging.WARNING):
            writer.write(
                EventRecord(
                    timestamp=datetime(2024, 7, 15, 14, 32, 5, tzinfo=timezone.utc),
                    event_type=EventType.NOISE,
                )
            )

        assert "Write buffer is full" in caplog.text


class TestDbWriterClose:
    """Tests for DbWriter.close()."""

    @patch("lightning_collector.db_writer.get_connection")
    def test_close_marks_disconnected(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """close() marks the writer as disconnected."""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        writer = DbWriter(settings)
        assert writer.is_connected is True

        writer.close()

        assert writer.is_connected is False
        mock_conn.close.assert_called_once()

    @patch("lightning_collector.db_writer.get_connection")
    def test_close_is_safe_when_disconnected(
        self, mock_get_conn: MagicMock, settings: CollectorSettings
    ) -> None:
        """close() does not raise when already disconnected."""
        import mariadb

        mock_get_conn.side_effect = mariadb.Error("Connection refused")

        writer = DbWriter(settings)
        writer.close()  # Should not raise
