"""MariaDB persistence component with in-memory write buffer.

The DbWriter inserts EventRecords into MariaDB. When the connection is
unavailable, records are buffered in a bounded deque and flushed once
connectivity is restored.
"""

from __future__ import annotations

import logging
from collections import deque

import mariadb

from lightning_common.config import CollectorSettings
from lightning_common.db import get_connection
from lightning_common.models import EventRecord

logger = logging.getLogger(__name__)

_INSERT_EVENT = (
    "INSERT INTO events (timestamp, event_type, distance_km, energy_normalized) "
    "VALUES (?, ?, ?, ?)"
)


class DbWriter:
    """Writes EventRecords to MariaDB with a bounded write buffer for resilience.

    When the database connection is unavailable, records are stored in an
    in-memory deque (max 10000 entries). Once connectivity is restored,
    buffered records are flushed in chronological order.

    Parameters
    ----------
    settings : CollectorSettings
        Configuration containing database connection parameters and buffer size.
    """

    def __init__(self, settings: CollectorSettings) -> None:
        self._settings = settings
        self._buffer: deque[EventRecord] = deque(maxlen=settings.buffer_max_size)
        self._conn: mariadb.Connection | None = None
        self._connected: bool = False

        # Attempt initial connection
        try:
            self._conn = get_connection(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                database=settings.db_name,
            )
            self._connected = True
        except mariadb.Error:
            logger.warning(
                "Initial MariaDB connection failed; records will be buffered"
            )
            self._connected = False

    @property
    def buffer_size(self) -> int:
        """Return the current number of records in the write buffer."""
        return len(self._buffer)

    @property
    def is_connected(self) -> bool:
        """Return whether the database connection is currently active."""
        return self._connected

    def write(self, record: EventRecord) -> None:
        """Write an EventRecord to MariaDB, or buffer it if unavailable.

        If connected, attempts a direct INSERT. On failure, the record is
        buffered and the connection is marked as lost.

        If not connected, the record is added to the write buffer. When the
        buffer is full, a warning is logged as the oldest record will be
        discarded by the deque's maxlen constraint.

        Parameters
        ----------
        record : EventRecord
            The event record to persist.
        """
        if self._connected:
            try:
                self._insert_record(record)
                return
            except mariadb.Error:
                logger.warning(
                    "MariaDB insert failed; buffering record and marking connection lost"
                )
                self._connected = False
                self._close_connection()

        # Buffer the record
        self._buffer_record(record)

    def flush_buffer(self) -> int:
        """Flush all buffered records to MariaDB in chronological order.

        Records are inserted one by one from oldest to newest. If an insert
        fails, remaining records stay in the buffer and the connection is
        marked as lost.

        Returns
        -------
        int
            The number of records successfully flushed.
        """
        if not self._connected or not self._buffer:
            return 0

        flushed = 0
        while self._buffer:
            record = self._buffer[0]  # Peek at oldest
            try:
                self._insert_record(record)
                self._buffer.popleft()  # Remove only after successful insert
                flushed += 1
            except mariadb.Error:
                logger.warning(
                    "MariaDB insert failed during buffer flush after %d records",
                    flushed,
                )
                self._connected = False
                self._close_connection()
                break

        if flushed > 0:
            logger.info("Flushed %d buffered records to MariaDB", flushed)

        return flushed

    def reconnect(self) -> bool:
        """Attempt to re-establish the MariaDB connection.

        Returns
        -------
        bool
            True if reconnection succeeded, False otherwise.
        """
        self._close_connection()

        try:
            self._conn = get_connection(
                host=self._settings.db_host,
                port=self._settings.db_port,
                user=self._settings.db_user,
                password=self._settings.db_password,
                database=self._settings.db_name,
            )
            self._connected = True
            logger.info("Reconnected to MariaDB")
            return True
        except mariadb.Error:
            logger.warning("MariaDB reconnection attempt failed")
            self._connected = False
            return False

    def close(self) -> None:
        """Close the database connection and release resources."""
        self._close_connection()
        self._connected = False

    def _insert_record(self, record: EventRecord) -> None:
        """Execute a parameterized INSERT for a single EventRecord.

        Parameters
        ----------
        record : EventRecord
            The event record to insert.

        Raises
        ------
        mariadb.Error
            If the INSERT statement fails.
        """
        if self._conn is None:
            raise mariadb.Error("No active connection")

        cursor = self._conn.cursor()
        try:
            cursor.execute(
                _INSERT_EVENT,
                (
                    record.timestamp,
                    record.event_type.value,
                    record.distance_km,
                    record.energy_normalized,
                ),
            )
            self._conn.commit()
        finally:
            cursor.close()

    def _buffer_record(self, record: EventRecord) -> None:
        """Add a record to the write buffer, logging if buffer is full.

        Parameters
        ----------
        record : EventRecord
            The event record to buffer.
        """
        if len(self._buffer) == self._buffer.maxlen:
            logger.warning(
                "Write buffer is full (%d records); oldest record will be discarded",
                self._buffer.maxlen,
            )

        self._buffer.append(record)

    def _close_connection(self) -> None:
        """Safely close the current database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except mariadb.Error:
                pass
            self._conn = None
