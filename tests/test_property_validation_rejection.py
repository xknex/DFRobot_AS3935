# Feature: as3935-modernization, Property 4: Input validation rejects invalid values without I2C writes
"""Property-based tests verifying that invalid parameter values are rejected
with ValueError before any I2C communication occurs.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from dfrobot_as3935.validators import (
    validate_capacitance,
    validate_noise_floor_level,
    validate_watchdog_threshold,
    validate_spike_rejection,
    validate_i2c_address,
    validate_lco_fdiv,
    validate_min_strikes,
)
from dfrobot_as3935.constants import (
    VALID_CAPACITANCE_RANGE,
    VALID_I2C_ADDRESSES,
    VALID_MIN_STRIKES,
)


# ---------------------------------------------------------------------------
# Strategies for generating invalid values
# ---------------------------------------------------------------------------

# Capacitance: valid values are {0, 8, 16, ..., 120}
# Invalid: negative, odd, >120, non-multiples of 8
_invalid_capacitance_integers = st.integers().filter(
    lambda x: x not in VALID_CAPACITANCE_RANGE
)

# Noise floor level: valid range 0-7
_invalid_noise_floor_integers = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=8),
)

# Watchdog threshold: valid range 0-15
_invalid_watchdog_integers = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=16),
)

# Spike rejection: valid range 0-15
_invalid_spike_rejection_integers = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=16),
)

# I2C address: valid values are {0x01, 0x02, 0x03}
_invalid_i2c_address_integers = st.integers().filter(
    lambda x: x not in VALID_I2C_ADDRESSES
)

# LCO fdiv: valid range 0-3
_invalid_lco_fdiv_integers = st.one_of(
    st.integers(max_value=-1),
    st.integers(min_value=4),
)

# Min strikes: valid values are {1, 5, 9, 16}
_invalid_min_strikes_values = st.one_of(
    st.integers().filter(lambda x: x not in VALID_MIN_STRIKES),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=1),
)

# Non-integer types for type-checking validators
_non_integer_types = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=1),
    st.lists(st.integers(), max_size=3),
    st.none(),
)


# ---------------------------------------------------------------------------
# Property tests: Invalid integer values
# ---------------------------------------------------------------------------


@pytest.mark.property
class TestCapacitanceRejection:
    """Property 4: validate_capacitance rejects invalid integer values."""

    @given(value=_invalid_capacitance_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer capacitance values raise ValueError."""
        with pytest.raises(ValueError, match="capacitance"):
            validate_capacitance(value)

    @given(value=_non_integer_types)
    @settings(max_examples=100)
    def test_rejects_non_integer_types(self, value) -> None:
        """Non-integer capacitance values raise ValueError."""
        with pytest.raises(ValueError, match="capacitance"):
            validate_capacitance(value)


@pytest.mark.property
class TestNoiseFloorLevelRejection:
    """Property 4: validate_noise_floor_level rejects invalid values."""

    @given(value=_invalid_noise_floor_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer noise floor values raise ValueError."""
        with pytest.raises(ValueError, match="noise_floor_level"):
            validate_noise_floor_level(value)

    @given(value=_non_integer_types)
    @settings(max_examples=100)
    def test_rejects_non_integer_types(self, value) -> None:
        """Non-integer noise floor values raise ValueError."""
        with pytest.raises(ValueError, match="noise_floor_level"):
            validate_noise_floor_level(value)


@pytest.mark.property
class TestWatchdogThresholdRejection:
    """Property 4: validate_watchdog_threshold rejects invalid values."""

    @given(value=_invalid_watchdog_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer watchdog threshold values raise ValueError."""
        with pytest.raises(ValueError, match="watchdog_threshold"):
            validate_watchdog_threshold(value)

    @given(value=_non_integer_types)
    @settings(max_examples=100)
    def test_rejects_non_integer_types(self, value) -> None:
        """Non-integer watchdog threshold values raise ValueError."""
        with pytest.raises(ValueError, match="watchdog_threshold"):
            validate_watchdog_threshold(value)


@pytest.mark.property
class TestSpikeRejectionRejection:
    """Property 4: validate_spike_rejection rejects invalid values."""

    @given(value=_invalid_spike_rejection_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer spike rejection values raise ValueError."""
        with pytest.raises(ValueError, match="spike_rejection"):
            validate_spike_rejection(value)

    @given(value=_non_integer_types)
    @settings(max_examples=100)
    def test_rejects_non_integer_types(self, value) -> None:
        """Non-integer spike rejection values raise ValueError."""
        with pytest.raises(ValueError, match="spike_rejection"):
            validate_spike_rejection(value)


@pytest.mark.property
class TestI2CAddressRejection:
    """Property 4: validate_i2c_address rejects invalid values."""

    @given(value=_invalid_i2c_address_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer I2C address values raise ValueError."""
        with pytest.raises(ValueError, match="i2c_address"):
            validate_i2c_address(value)


@pytest.mark.property
class TestLcoFdivRejection:
    """Property 4: validate_lco_fdiv rejects invalid values."""

    @given(value=_invalid_lco_fdiv_integers)
    @settings(max_examples=100)
    def test_rejects_invalid_integers(self, value: int) -> None:
        """Out-of-range integer LCO fdiv values raise ValueError."""
        with pytest.raises(ValueError, match="lco_fdiv"):
            validate_lco_fdiv(value)

    @given(value=_non_integer_types)
    @settings(max_examples=100)
    def test_rejects_non_integer_types(self, value) -> None:
        """Non-integer LCO fdiv values raise ValueError."""
        with pytest.raises(ValueError, match="lco_fdiv"):
            validate_lco_fdiv(value)


@pytest.mark.property
class TestMinStrikesRejection:
    """Property 4: validate_min_strikes rejects invalid values."""

    @given(value=_invalid_min_strikes_values)
    @settings(max_examples=100)
    def test_rejects_invalid_values(self, value) -> None:
        """Invalid min strikes values (wrong integers, floats, strings) raise ValueError."""
        with pytest.raises(ValueError, match="min_strikes"):
            validate_min_strikes(value)
