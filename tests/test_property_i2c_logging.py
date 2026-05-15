# Feature: as3935-modernization, Property 10: I2C operations emit DEBUG log
"""Property-based test verifying that I2C read and write operations emit
DEBUG log records containing the register address and value.

**Validates: Requirements 9.3**
"""

import logging
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from dfrobot_as3935.sensor import DFRobot_AS3935


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid register addresses per AS3935 datasheet (0x00–0x08, 0x3C, 0x3D)
_valid_registers = st.sampled_from(
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x3C, 0x3D]
)

# Any byte value (0–255)
_byte_values = st.integers(min_value=0, max_value=255)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestI2COperationsEmitDebugLog:
    """Property 10: I2C operations emit DEBUG log.

    For any register read or write operation, the library SHALL emit a log
    record at DEBUG level containing the register address and the value
    read or written.
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_read_register_emits_debug_log(
        self, register: int, value: int
    ) -> None:
        """_read_register emits a DEBUG log with register address and value."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = value

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act: capture log records at DEBUG level using a custom handler
        logger = logging.getLogger("dfrobot_as3935")
        original_level = logger.level
        logger.setLevel(logging.DEBUG)

        records: list[logging.LogRecord] = []

        class RecordCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        capture = RecordCapture()
        capture.setLevel(logging.DEBUG)
        logger.addHandler(capture)

        try:
            sensor._read_register(register)
        finally:
            logger.removeHandler(capture)
            logger.setLevel(original_level)

        # Assert: at least one DEBUG record contains register address and value
        debug_records = [r for r in records if r.levelno == logging.DEBUG]
        assert len(debug_records) >= 1, (
            f"Expected at least one DEBUG log record for read of "
            f"register 0x{register:02X}, value 0x{value:02X}"
        )

        # Verify the log message contains register address and value in hex
        reg_hex = f"0x{register:02X}"
        val_hex = f"0x{value:02X}"
        matching = [
            r for r in debug_records
            if reg_hex in r.getMessage() and val_hex in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"Expected DEBUG log containing register={reg_hex} and "
            f"value={val_hex}, got messages: "
            f"{[r.getMessage() for r in debug_records]}"
        )

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_write_register_emits_debug_log(
        self, register: int, value: int
    ) -> None:
        """_write_register emits a DEBUG log with register address and value."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act: capture log records at DEBUG level
        logger = logging.getLogger("dfrobot_as3935")

        records: list[logging.LogRecord] = []

        class RecordCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        capture = RecordCapture()
        capture.setLevel(logging.DEBUG)
        logger.addHandler(capture)
        logger.setLevel(logging.DEBUG)

        try:
            sensor._write_register(register, value)
        finally:
            logger.removeHandler(capture)

        # Assert: at least one DEBUG record contains register address and value
        debug_records = [r for r in records if r.levelno == logging.DEBUG]
        assert len(debug_records) >= 1, (
            f"Expected at least one DEBUG log record for write of "
            f"register 0x{register:02X}, value 0x{value:02X}"
        )

        # Verify the log message contains register address and value in hex
        reg_hex = f"0x{register:02X}"
        val_hex = f"0x{value:02X}"
        matching = [
            r for r in debug_records
            if reg_hex in r.getMessage() and val_hex in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"Expected DEBUG log containing register={reg_hex} and "
            f"value={val_hex}, got messages: "
            f"{[r.getMessage() for r in debug_records]}"
        )
