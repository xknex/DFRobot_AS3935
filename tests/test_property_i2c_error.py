# Feature: as3935-modernization, Property 3: I2C errors include diagnostic context
"""Property-based tests verifying that I2C errors are re-raised with diagnostic
context including register address, device address, and original error description.

**Validates: Requirements 1.4**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from dfrobot_as3935.sensor import DFRobot_AS3935


# ---------------------------------------------------------------------------
# Strategies for generating valid register and device addresses
# ---------------------------------------------------------------------------

_register_addresses = st.sampled_from(
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x3C, 0x3D]
)

_device_addresses = st.sampled_from([0x01, 0x02, 0x03])


# ---------------------------------------------------------------------------
# Property tests: I2C error context
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestI2CReadErrorContext:
    """Property 3: _read_register re-raises OSError with diagnostic context."""

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_read_error_contains_register_address(
        self, register: int, address: int
    ) -> None:
        """OSError from _read_register contains the register address in hex."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.read_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._read_register(register)

        error_msg = str(exc_info.value).lower()
        assert f"0x{register:02x}" in error_msg

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_read_error_contains_device_address(
        self, register: int, address: int
    ) -> None:
        """OSError from _read_register contains the device address in hex."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.read_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._read_register(register)

        error_msg = str(exc_info.value).lower()
        assert f"0x{address:02x}" in error_msg

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_read_error_contains_original_error(
        self, register: int, address: int
    ) -> None:
        """OSError from _read_register contains the original error text."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.read_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._read_register(register)

        error_msg = str(exc_info.value)
        assert "test error" in error_msg


@pytest.mark.property
class TestI2CWriteErrorContext:
    """Property 3: _write_register re-raises OSError with diagnostic context."""

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_write_error_contains_register_address(
        self, register: int, address: int
    ) -> None:
        """OSError from _write_register contains the register address in hex."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.write_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._write_register(register, 0x42)

        error_msg = str(exc_info.value).lower()
        assert f"0x{register:02x}" in error_msg

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_write_error_contains_device_address(
        self, register: int, address: int
    ) -> None:
        """OSError from _write_register contains the device address in hex."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.write_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._write_register(register, 0x42)

        error_msg = str(exc_info.value).lower()
        assert f"0x{address:02x}" in error_msg

    @given(register=_register_addresses, address=_device_addresses)
    @settings(max_examples=100)
    def test_write_error_contains_original_error(
        self, register: int, address: int
    ) -> None:
        """OSError from _write_register contains the original error text."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.write_byte_data.side_effect = OSError("test error")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._write_register(register, 0x42)

        error_msg = str(exc_info.value)
        assert "test error" in error_msg
