# Feature: as3935-modernization, Property 5: Input validation accepts all valid values
"""Property-based tests verifying that all valid parameter values are accepted
by the validators without raising ValueError.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**
"""

import pytest
from hypothesis import given, settings
from hypothesis.strategies import integers, sampled_from

from dfrobot_as3935.validators import (
    validate_capacitance,
    validate_i2c_address,
    validate_lco_fdiv,
    validate_min_strikes,
    validate_noise_floor_level,
    validate_spike_rejection,
    validate_watchdog_threshold,
)


@pytest.mark.property
@settings(max_examples=100)
@given(value=sampled_from([0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96, 104, 112, 120]))
def test_validate_capacitance_accepts_valid_values(value: int) -> None:
    """For any capacitance value in {0, 8, 16, ..., 120}, no ValueError is raised."""
    # Should return None without raising
    result = validate_capacitance(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=integers(min_value=0, max_value=7))
def test_validate_noise_floor_level_accepts_valid_values(value: int) -> None:
    """For any noise floor level in 0–7, no ValueError is raised."""
    result = validate_noise_floor_level(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=integers(min_value=0, max_value=15))
def test_validate_watchdog_threshold_accepts_valid_values(value: int) -> None:
    """For any watchdog threshold in 0–15, no ValueError is raised."""
    result = validate_watchdog_threshold(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=integers(min_value=0, max_value=15))
def test_validate_spike_rejection_accepts_valid_values(value: int) -> None:
    """For any spike rejection value in 0–15, no ValueError is raised."""
    result = validate_spike_rejection(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=sampled_from([0x01, 0x02, 0x03]))
def test_validate_i2c_address_accepts_valid_values(value: int) -> None:
    """For any I2C address in {0x01, 0x02, 0x03}, no ValueError is raised."""
    result = validate_i2c_address(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=integers(min_value=0, max_value=3))
def test_validate_lco_fdiv_accepts_valid_values(value: int) -> None:
    """For any LCO frequency division ratio in 0–3, no ValueError is raised."""
    result = validate_lco_fdiv(value)
    assert result is None


@pytest.mark.property
@settings(max_examples=100)
@given(value=sampled_from([1, 5, 9, 16]))
def test_validate_min_strikes_accepts_valid_values(value: int) -> None:
    """For any min strikes value in {1, 5, 9, 16}, no ValueError is raised."""
    result = validate_min_strikes(value)
    assert result is None
