"""Collector daemon main loop for the Lightning Collector Service.

Listens for AS3935 interrupt events, constructs EventRecords, and persists
them to both a local CSV file and a remote MariaDB database. Handles
graceful shutdown on SIGTERM and background reconnection for both the
database and sensor.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone

from dfrobot_as3935.sensor import DFRobot_AS3935
from lightning_collector.csv_writer import CsvWriter
from lightning_collector.db_writer import DbWriter
from lightning_common.config import CollectorSettings
from lightning_common.db import create_tables_if_not_exist, get_connection_from_settings
from lightning_common.models import EventRecord, EventType

logger = logging.getLogger(__name__)

# Interrupt source codes from the AS3935 datasheet
_INT_LIGHTNING = 0x08
_INT_DISTURBER = 0x04
_INT_NOISE = 0x01

# Reconnection intervals
_DB_RECONNECT_INTERVAL_S = 10.0
_SENSOR_RECONNECT_INTERVAL_S = 30.0

# Shutdown timeout for DB buffer flush
_SHUTDOWN_DB_FLUSH_TIMEOUT_S = 5.0


def _mask_password(password: str) -> str:
    """Mask a password for safe logging."""
    if len(password) <= 2:
        return "***"
    return password[0] + "***" + password[-1]


def _log_configuration(settings: CollectorSettings) -> None:
    """Log the collector configuration with masked credentials."""
    logger.info("Collector configuration:")
    logger.info("  db_host: %s", settings.db_host)
    logger.info("  db_port: %d", settings.db_port)
    logger.info("  db_user: %s", settings.db_user)
    logger.info("  db_password: %s", _mask_password(settings.db_password))
    logger.info("  db_name: %s", settings.db_name)
    logger.info("  csv_file_path: %s", settings.csv_file_path)
    logger.info("  sensor_i2c_address: %#04x", settings.sensor_i2c_address)
    logger.info("  sensor_i2c_bus: %d", settings.sensor_i2c_bus)
    logger.info("  sensor_irq_pin: %d", settings.sensor_irq_pin)
    logger.info("  buffer_max_size: %d", settings.buffer_max_size)


def _map_interrupt_source(source: int) -> EventType | None:
    """Map an AS3935 interrupt source code to an EventType.

    Returns None if the source code is unrecognized.
    """
    if source == _INT_LIGHTNING:
        return EventType.LIGHTNING
    elif source == _INT_DISTURBER:
        return EventType.DISTURBER
    elif source == _INT_NOISE:
        return EventType.NOISE
    return None


class LightningCollector:
    """Main collector daemon that orchestrates sensor reading and persistence.

    Manages the lifecycle of the sensor, CSV writer, and DB writer components.
    Handles interrupt callbacks, background reconnection, and graceful shutdown.
    """

    def __init__(self, settings: CollectorSettings) -> None:
        self._settings = settings
        self._shutdown_event = threading.Event()
        self._sensor: DFRobot_AS3935 | None = None
        self._sensor_connected = False
        self._csv_writer: CsvWriter | None = None
        self._db_writer: DbWriter | None = None
        self._last_db_reconnect: float = 0.0
        self._last_sensor_reconnect: float = 0.0

    def run(self) -> None:
        """Run the collector daemon main loop.

        Initializes all components, registers the interrupt callback,
        and enters the main loop. Exits cleanly on SIGTERM.
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )

        _log_configuration(self._settings)

        # Register SIGTERM handler
        signal.signal(signal.SIGTERM, self._sigterm_handler)

        # Initialize components
        self._init_sensor()
        self._init_csv_writer()
        self._init_db_writer()
        self._create_db_tables()

        # Register interrupt callback
        if self._sensor is not None:
            self._sensor.register_interrupt_callback(self._on_interrupt)
            logger.info("Interrupt callback registered with sensor")

        logger.info("Collector daemon started, waiting for events...")

        # Main loop: wait for shutdown, periodically attempt reconnections
        self._main_loop()

        # Shutdown sequence
        self._shutdown()

    def _main_loop(self) -> None:
        """Main loop that waits for shutdown while performing reconnections."""
        while not self._shutdown_event.is_set():
            # Wait with a short timeout to allow periodic reconnection checks
            self._shutdown_event.wait(timeout=1.0)

            if self._shutdown_event.is_set():
                break

            now = time.monotonic()

            # DB reconnection every 10s
            if (
                self._db_writer is not None
                and not self._db_writer.is_connected
                and (now - self._last_db_reconnect) >= _DB_RECONNECT_INTERVAL_S
            ):
                self._last_db_reconnect = now
                logger.info("Attempting MariaDB reconnection...")
                if self._db_writer.reconnect():
                    self._db_writer.flush_buffer()

            # Sensor reconnection every 30s
            if (
                not self._sensor_connected
                and (now - self._last_sensor_reconnect) >= _SENSOR_RECONNECT_INTERVAL_S
            ):
                self._last_sensor_reconnect = now
                logger.info("Attempting sensor reconnection...")
                self._reconnect_sensor()

    def _on_interrupt(self) -> None:
        """Interrupt callback invoked by gpiozero when the sensor IRQ fires.

        Reads the interrupt source, constructs an EventRecord, and writes
        it to both CSV and DB.
        """
        if self._sensor is None:
            return

        try:
            source = self._sensor.get_interrupt_source()
        except (OSError, RuntimeError) as exc:
            logger.error("Failed to read interrupt source: %s", exc)
            self._sensor_connected = False
            return

        event_type = _map_interrupt_source(source)
        if event_type is None:
            logger.warning("Unknown interrupt source: %#04x", source)
            return

        # Build EventRecord
        timestamp = datetime.now(timezone.utc)
        distance_km: int | None = None
        energy_normalized: float | None = None

        if event_type == EventType.LIGHTNING:
            try:
                distance_km = self._sensor.get_lightning_distance_km()
                energy_normalized = self._sensor.get_strike_energy_normalized()
            except (OSError, RuntimeError) as exc:
                logger.error("Failed to read lightning data: %s", exc)
                # Still record the event with None values
                pass

        record = EventRecord(
            timestamp=timestamp,
            event_type=event_type,
            distance_km=distance_km,
            energy_normalized=energy_normalized,
        )

        logger.info(
            "Event detected: %s (distance=%s km, energy=%s)",
            event_type.value,
            distance_km,
            energy_normalized,
        )

        # Write to CSV first (local, reliable)
        if self._csv_writer is not None:
            self._csv_writer.write(record)

        # Write to DB (best-effort with buffering)
        if self._db_writer is not None:
            self._db_writer.write(record)

    def _sigterm_handler(self, signum: int, frame: object) -> None:
        """Handle SIGTERM signal for graceful shutdown."""
        logger.info("SIGTERM received, initiating graceful shutdown...")
        self._shutdown_event.set()

    def _shutdown(self) -> None:
        """Perform graceful shutdown: flush CSV, attempt DB flush, close all."""
        logger.info("Shutting down collector...")

        # Unregister interrupt callback
        if self._sensor is not None:
            try:
                self._sensor.register_interrupt_callback(None)
            except Exception:
                pass

        # Flush CSV writer
        if self._csv_writer is not None:
            try:
                self._csv_writer.close()
                logger.info("CSV writer closed")
            except Exception:
                logger.exception("Error closing CSV writer")

        # Attempt DB buffer flush within 5s timeout
        if self._db_writer is not None:
            if self._db_writer.buffer_size > 0:
                logger.info(
                    "Attempting to flush %d buffered records to DB...",
                    self._db_writer.buffer_size,
                )
                flush_thread = threading.Thread(
                    target=self._flush_db_with_reconnect, daemon=True
                )
                flush_thread.start()
                flush_thread.join(timeout=_SHUTDOWN_DB_FLUSH_TIMEOUT_S)
                if flush_thread.is_alive():
                    logger.warning(
                        "DB buffer flush timed out after %.1fs",
                        _SHUTDOWN_DB_FLUSH_TIMEOUT_S,
                    )

            self._db_writer.close()
            logger.info("DB writer closed")

        # Close sensor
        if self._sensor is not None:
            try:
                self._sensor.close()
                logger.info("Sensor closed")
            except Exception:
                logger.exception("Error closing sensor")

        logger.info("Collector shutdown complete")

    def _flush_db_with_reconnect(self) -> None:
        """Attempt to reconnect and flush the DB buffer (used during shutdown)."""
        if self._db_writer is None:
            return

        if not self._db_writer.is_connected:
            self._db_writer.reconnect()

        if self._db_writer.is_connected:
            self._db_writer.flush_buffer()

    def _init_sensor(self) -> None:
        """Initialize the AS3935 sensor and confirm connectivity."""
        try:
            self._sensor = DFRobot_AS3935(
                address=self._settings.sensor_i2c_address,
                bus=self._settings.sensor_i2c_bus,
                irq_pin=self._settings.sensor_irq_pin,
            )
            self._sensor_connected = True
            logger.info(
                "Sensor connected (I2C address=%#04x, bus=%d, IRQ pin=%d)",
                self._settings.sensor_i2c_address,
                self._settings.sensor_i2c_bus,
                self._settings.sensor_irq_pin,
            )
        except (OSError, RuntimeError) as exc:
            logger.error("Failed to initialize sensor: %s", exc)
            self._sensor = None
            self._sensor_connected = False

    def _reconnect_sensor(self) -> None:
        """Attempt to reconnect the sensor."""
        # Close existing sensor if any
        if self._sensor is not None:
            try:
                self._sensor.close()
            except Exception:
                pass
            self._sensor = None

        try:
            self._sensor = DFRobot_AS3935(
                address=self._settings.sensor_i2c_address,
                bus=self._settings.sensor_i2c_bus,
                irq_pin=self._settings.sensor_irq_pin,
            )
            self._sensor.register_interrupt_callback(self._on_interrupt)
            self._sensor_connected = True
            logger.info("Sensor reconnected successfully")
        except (OSError, RuntimeError) as exc:
            logger.warning("Sensor reconnection failed: %s", exc)
            self._sensor = None
            self._sensor_connected = False

    def _init_csv_writer(self) -> None:
        """Initialize the CSV writer."""
        try:
            self._csv_writer = CsvWriter(self._settings.csv_file_path)
            logger.info("CSV writer initialized: %s", self._settings.csv_file_path)
        except Exception:
            logger.exception("Failed to initialize CSV writer")
            self._csv_writer = None

    def _init_db_writer(self) -> None:
        """Initialize the DB writer."""
        try:
            self._db_writer = DbWriter(self._settings)
            if self._db_writer.is_connected:
                logger.info("DB writer initialized and connected")
            else:
                logger.warning(
                    "DB writer initialized but not connected; records will be buffered"
                )
        except Exception:
            logger.exception("Failed to initialize DB writer")
            self._db_writer = None

    def _create_db_tables(self) -> None:
        """Create database tables if they don't exist."""
        if self._db_writer is None or not self._db_writer.is_connected:
            logger.warning("Skipping table creation: DB not connected")
            return

        try:
            conn = get_connection_from_settings(self._settings)
            create_tables_if_not_exist(conn)
            conn.close()
        except Exception:
            logger.exception("Failed to create database tables")


def main() -> None:
    """Entry point for the Lightning Collector Service."""
    try:
        settings = CollectorSettings()  # type: ignore[call-arg]
    except Exception as exc:
        logging.basicConfig(level=logging.ERROR)
        logger.error("Failed to load configuration: %s", exc)
        sys.exit(1)

    collector = LightningCollector(settings)
    collector.run()
    sys.exit(0)
