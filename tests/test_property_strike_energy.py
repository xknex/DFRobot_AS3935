# Feature: as3935-modernization, Property 6: Strike energy assembly and normalization
"""Property-based test verifying that strike energy is correctly assembled
from three register bytes and normalized to [0.0, 1.0].

**Validates: Requirements 6.3, 6.4**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock

from dfrobot_as3935.sensor import DFRobot_AS3935
from dfrobot_as3935.constants import REG_ENERGY_LSB, REG_ENERGY_MSB, REG_ENERGY_MMSB


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# LSB: full byte range 0–255
_lsb_values = st.integers(min_value=0, max_value=255)

# MSB: full byte range 0–255
_msb_values = st.integers(min_value=0, max_value=255)

# MMSB: only bits 4:0 are used, so 0–31
_mmsb_values = st.integers(min_value=0, max_value=31)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestStrikeEnergyAssemblyAndNormalization:
    """Property 6: Strike energy assembly and normalization.

    For any three byte values (LSB: 0–255, MSB: 0–255, MMSB: 0–31),
    the raw energy SHALL equal (MMSB << 16) | (MSB << 8) | LSB (a 21-bit
    unsigned integer in range 0–2,097,151), and the normalized energy SHALL
    equal raw / 2,097,151 (a float in range [0.0, 1.0]).
    """

    @given(lsb=_lsb_values, msb=_msb_values, mmsb=_mmsb_values)
    @settings(max_examples=100)
    def test_raw_energy_assembly(self, lsb: int, msb: int, mmsb: int) -> None:
        """get_strike_energy_raw assembles (MMSB << 16) | (MSB << 8) | LSB."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()

        def read_byte_data_side_effect(address: int, register: int) -> int:
            if register == REG_ENERGY_LSB:
                return lsb
            elif register == REG_ENERGY_MSB:
                return msb
            elif register == REG_ENERGY_MMSB:
                return mmsb
            return 0x00

        mock_smbus.read_byte_data.side_effect = read_byte_data_side_effect

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act
        raw = sensor.get_strike_energy_raw()

        # Assert: raw equals the expected 21-bit assembly
        expected_raw = (mmsb << 16) | (msb << 8) | lsb
        assert raw == expected_raw

        # Assert: raw is within valid 21-bit range
        assert 0 <= raw <= 2_097_151

    @given(lsb=_lsb_values, msb=_msb_values, mmsb=_mmsb_values)
    @settings(max_examples=100)
    def test_normalized_energy_in_range(self, lsb: int, msb: int, mmsb: int) -> None:
        """get_strike_energy_normalized returns raw / 2,097,151 in [0.0, 1.0]."""
        # Arrange: create sensor with mocked bus
        mock_smbus = MagicMock()

        def read_byte_data_side_effect(address: int, register: int) -> int:
            if register == REG_ENERGY_LSB:
                return lsb
            elif register == REG_ENERGY_MSB:
                return msb
            elif register == REG_ENERGY_MMSB:
                return mmsb
            return 0x00

        mock_smbus.read_byte_data.side_effect = read_byte_data_side_effect

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        # Act
        normalized = sensor.get_strike_energy_normalized()

        # Assert: normalized equals raw / 2,097,151
        expected_raw = (mmsb << 16) | (msb << 8) | lsb
        expected_normalized = expected_raw / 2_097_151
        assert normalized == pytest.approx(expected_normalized)

        # Assert: normalized is within [0.0, 1.0]
        assert 0.0 <= normalized <= 1.0
