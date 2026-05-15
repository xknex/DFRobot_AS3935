# Feature: as3935-modernization, Property 2: Register write sends correct data
"""Property-based tests verifying that _write_register calls write_byte_data
with the correct device address, register address, and value.

**Validates: Requirements 1.3**
"""

from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dfrobot_as3935.sensor import DFRobot_AS3935


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid register addresses per AS3935 datasheet
_valid_registers = st.sampled_from(
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x3C, 0x3D]
)

# Any valid byte value
_byte_values = st.integers(min_value=0, max_value=255)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestRegisterWriteSendsCorrectData:
    """Property 2: Register write sends correct data.

    For any valid register address and any byte value, _write_register
    SHALL call write_byte_data with the correct device address, register
    address, and value.
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_write_register_calls_write_byte_data_correctly(
        self, register: int, value: int
    ) -> None:
        """_write_register calls write_byte_data with (address, register, value)."""
        # Arrange: create sensor with mocked bus
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        sensor._bus = mock_bus

        # Act
        sensor._write_register(register, value)

        # Assert
        mock_bus.write_byte_data.assert_called_once_with(0x03, register, value)
