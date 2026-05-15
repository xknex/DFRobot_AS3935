# Feature: as3935-modernization, Property 1: Register read returns correct value
"""Property-based test verifying that _read_register returns the exact byte
value from the I2C bus for any valid register address.

**Validates: Requirements 1.2**
"""

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

# Any byte value that the I2C bus could return
_byte_values = st.integers(min_value=0, max_value=255)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestRegisterReadReturnsCorrectValue:
    """Property 1: Register read returns correct value.

    For any valid register address and any byte value returned by the
    mocked I2C bus, _read_register SHALL return the exact byte value
    and call read_byte_data with the correct device address and register.
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_read_register_returns_exact_value(
        self, register: int, value: int
    ) -> None:
        """_read_register returns the exact byte value from read_byte_data."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = value

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act
        result = sensor._read_register(register)

        # Assert: return value matches exactly
        assert result == value

        # Assert: read_byte_data called with correct arguments
        mock_smbus.read_byte_data.assert_called_once_with(0x03, register)
