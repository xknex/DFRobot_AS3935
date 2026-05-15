"""Unit tests for input validation functions.

Tests each validator with valid inputs (no exception raised) and invalid
inputs (ValueError raised with informative message containing parameter
name, provided value, and valid constraint).
"""

import pytest

from dfrobot_as3935.validators import (
    validate_capacitance,
    validate_i2c_address,
    validate_lco_fdiv,
    validate_min_strikes,
    validate_noise_floor_level,
    validate_spike_rejection,
    validate_watchdog_threshold,
)


# --- validate_capacitance ---


class TestValidateCapacitance:
    """Tests for validate_capacitance."""

    @pytest.mark.parametrize("value", [0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120])
    def test_valid_values(self, value: int) -> None:
        """Valid capacitance values (multiples of 8, 0–120) do not raise."""
        validate_capacitance(value)  # Should not raise

    @pytest.mark.parametrize("value", [1, 7, 121, -1])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="capacitance"):
            validate_capacitance(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError with type info."""
        with pytest.raises(ValueError, match="capacitance.*integer"):
            validate_capacitance("string")  # type: ignore[arg-type]

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="7"):
            validate_capacitance(7)

    def test_error_message_contains_constraint(self) -> None:
        """Error message includes the valid constraint."""
        with pytest.raises(ValueError, match="multiple of 8.*0–120"):
            validate_capacitance(5)


# --- validate_noise_floor_level ---


class TestValidateNoiseFloorLevel:
    """Tests for validate_noise_floor_level."""

    @pytest.mark.parametrize("value", range(8))
    def test_valid_values(self, value: int) -> None:
        """Valid noise floor levels (0–7) do not raise."""
        validate_noise_floor_level(value)  # Should not raise

    @pytest.mark.parametrize("value", [-1, 8])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="noise_floor_level"):
            validate_noise_floor_level(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="noise_floor_level.*integer"):
            validate_noise_floor_level("string")  # type: ignore[arg-type]

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="8"):
            validate_noise_floor_level(8)

    def test_error_message_contains_constraint(self) -> None:
        """Error message includes the valid range."""
        with pytest.raises(ValueError, match="0–7"):
            validate_noise_floor_level(10)


# --- validate_watchdog_threshold ---


class TestValidateWatchdogThreshold:
    """Tests for validate_watchdog_threshold."""

    @pytest.mark.parametrize("value", range(16))
    def test_valid_values(self, value: int) -> None:
        """Valid watchdog thresholds (0–15) do not raise."""
        validate_watchdog_threshold(value)  # Should not raise

    @pytest.mark.parametrize("value", [-1, 16])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="watchdog_threshold"):
            validate_watchdog_threshold(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="watchdog_threshold.*integer"):
            validate_watchdog_threshold("string")  # type: ignore[arg-type]

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="16"):
            validate_watchdog_threshold(16)

    def test_error_message_contains_constraint(self) -> None:
        """Error message includes the valid range."""
        with pytest.raises(ValueError, match="0–15"):
            validate_watchdog_threshold(20)


# --- validate_spike_rejection ---


class TestValidateSpikeRejection:
    """Tests for validate_spike_rejection."""

    @pytest.mark.parametrize("value", range(16))
    def test_valid_values(self, value: int) -> None:
        """Valid spike rejection values (0–15) do not raise."""
        validate_spike_rejection(value)  # Should not raise

    @pytest.mark.parametrize("value", [-1, 16])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="spike_rejection"):
            validate_spike_rejection(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="spike_rejection.*integer"):
            validate_spike_rejection("string")  # type: ignore[arg-type]

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="-1"):
            validate_spike_rejection(-1)

    def test_error_message_contains_constraint(self) -> None:
        """Error message includes the valid range."""
        with pytest.raises(ValueError, match="0–15"):
            validate_spike_rejection(20)


# --- validate_i2c_address ---


class TestValidateI2cAddress:
    """Tests for validate_i2c_address."""

    @pytest.mark.parametrize("value", [0x01, 0x02, 0x03])
    def test_valid_values(self, value: int) -> None:
        """Valid I2C addresses (0x01, 0x02, 0x03) do not raise."""
        validate_i2c_address(value)  # Should not raise

    @pytest.mark.parametrize("value", [0x00, 0x04])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="i2c_address"):
            validate_i2c_address(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="i2c_address"):
            validate_i2c_address("string")  # type: ignore[arg-type]

    def test_error_message_contains_valid_set(self) -> None:
        """Error message includes the set of valid addresses."""
        with pytest.raises(ValueError, match="0x1.*0x2.*0x3"):
            validate_i2c_address(0x05)

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value in hex."""
        with pytest.raises(ValueError, match="0x0"):
            validate_i2c_address(0x00)


# --- validate_lco_fdiv ---


class TestValidateLcoFdiv:
    """Tests for validate_lco_fdiv."""

    @pytest.mark.parametrize("value", [0, 1, 2, 3])
    def test_valid_values(self, value: int) -> None:
        """Valid LCO fdiv values (0–3) do not raise."""
        validate_lco_fdiv(value)  # Should not raise

    @pytest.mark.parametrize("value", [-1, 4])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="lco_fdiv"):
            validate_lco_fdiv(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="lco_fdiv.*integer"):
            validate_lco_fdiv("string")  # type: ignore[arg-type]

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="4"):
            validate_lco_fdiv(4)

    def test_error_message_contains_constraint(self) -> None:
        """Error message includes the valid range."""
        with pytest.raises(ValueError, match="0–3"):
            validate_lco_fdiv(5)


# --- validate_min_strikes ---


class TestValidateMinStrikes:
    """Tests for validate_min_strikes."""

    @pytest.mark.parametrize("value", [1, 5, 9, 16])
    def test_valid_values(self, value: int) -> None:
        """Valid min strikes values (1, 5, 9, 16) do not raise."""
        validate_min_strikes(value)  # Should not raise

    @pytest.mark.parametrize("value", [0, 2, 3, 17])
    def test_invalid_integer_values(self, value: int) -> None:
        """Out-of-range integer values raise ValueError."""
        with pytest.raises(ValueError, match="min_strikes"):
            validate_min_strikes(value)

    def test_invalid_type_string(self) -> None:
        """Non-integer type raises ValueError."""
        with pytest.raises(ValueError, match="min_strikes"):
            validate_min_strikes("string")  # type: ignore[arg-type]

    def test_error_message_contains_valid_set(self) -> None:
        """Error message includes the set of valid values."""
        with pytest.raises(ValueError, match="1.*5.*9.*16"):
            validate_min_strikes(7)

    def test_error_message_contains_value(self) -> None:
        """Error message includes the invalid value."""
        with pytest.raises(ValueError, match="0"):
            validate_min_strikes(0)
