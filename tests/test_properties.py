# Feature: as3935-modernization — Consolidated Property-Based Tests (Properties 1–10)
"""Consolidated property-based tests for the DFRobot AS3935 library.

This module contains all 10 Hypothesis property tests defined in the design
document. Each test uses @given and @settings(max_examples=100) to ensure
a minimum of 100 iterations per property.

**Validates: Requirements 13.1**
"""

import logging
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from dfrobot_as3935.constants import (
    REG_ENERGY_LSB,
    REG_ENERGY_MSB,
    REG_ENERGY_MMSB,
    VALID_CAPACITANCE_RANGE,
    VALID_I2C_ADDRESSES,
    VALID_MIN_STRIKES,
)
from dfrobot_as3935.sensor import DFRobot_AS3935
from dfrobot_as3935.validators import (
    validate_capacitance,
    validate_i2c_address,
    validate_lco_fdiv,
    validate_min_strikes,
    validate_noise_floor_level,
    validate_spike_rejection,
    validate_watchdog_threshold,
)


# ===========================================================================
# Shared Strategies
# ===========================================================================

# Valid register addresses per AS3935 datasheet (0x00–0x08, 0x3C, 0x3D)
_valid_registers = st.sampled_from(
    [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x3C, 0x3D]
)

# Valid device I2C addresses
_device_addresses = st.sampled_from([0x01, 0x02, 0x03])

# Any valid byte value (0–255)
_byte_values = st.integers(min_value=0, max_value=255)


# ===========================================================================
# Property 1: Register read returns correct value
# ===========================================================================


@pytest.mark.property
class TestProperty1RegisterRead:
    """Property 1: Register read returns correct value.

    For any valid register address and any byte value returned by the mocked
    I2C bus, _read_register SHALL call read_byte_data with the correct device
    address and register address, and return the exact byte value.

    **Validates: Requirements 1.2**
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_read_register_returns_exact_value(
        self, register: int, value: int
    ) -> None:
        """_read_register returns the exact byte value from read_byte_data."""
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = value

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        result = sensor._read_register(register)

        assert result == value
        mock_smbus.read_byte_data.assert_called_once_with(0x03, register)


# ===========================================================================
# Property 2: Register write sends correct data
# ===========================================================================


@pytest.mark.property
class TestProperty2RegisterWrite:
    """Property 2: Register write sends correct data.

    For any valid register address and any byte value, _write_register SHALL
    call write_byte_data with the correct device address, register address,
    and value.

    **Validates: Requirements 1.3**
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100)
    def test_write_register_calls_write_byte_data_correctly(
        self, register: int, value: int
    ) -> None:
        """_write_register calls write_byte_data with (address, register, value)."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        sensor._bus = mock_bus

        sensor._write_register(register, value)

        mock_bus.write_byte_data.assert_called_once_with(0x03, register, value)


# ===========================================================================
# Property 3: I2C errors include diagnostic context
# ===========================================================================


@pytest.mark.property
class TestProperty3I2CErrorContext:
    """Property 3: I2C errors include diagnostic context.

    For any valid register address and device address, when the I2C bus raises
    an OSError, the library SHALL re-raise an OSError whose message contains
    the register address, the device I2C address, and the original error
    description.

    **Validates: Requirements 1.4**
    """

    @given(register=_valid_registers, address=_device_addresses)
    @settings(max_examples=100)
    def test_read_error_contains_diagnostic_context(
        self, register: int, address: int
    ) -> None:
        """OSError from _read_register contains register, device address, and cause."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.read_byte_data.side_effect = OSError("bus fault")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._read_register(register)

        error_msg = str(exc_info.value).lower()
        assert f"0x{register:02x}" in error_msg
        assert f"0x{address:02x}" in error_msg
        assert "bus fault" in error_msg

    @given(register=_valid_registers, address=_device_addresses)
    @settings(max_examples=100)
    def test_write_error_contains_diagnostic_context(
        self, register: int, address: int
    ) -> None:
        """OSError from _write_register contains register, device address, and cause."""
        sensor = DFRobot_AS3935(address=address, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.write_byte_data.side_effect = OSError("bus fault")
        sensor._bus = mock_bus

        with pytest.raises(OSError) as exc_info:
            sensor._write_register(register, 0x42)

        error_msg = str(exc_info.value).lower()
        assert f"0x{register:02x}" in error_msg
        assert f"0x{address:02x}" in error_msg
        assert "bus fault" in error_msg


# ===========================================================================
# Property 4: Input validation rejects invalid values without I2C writes
# ===========================================================================

# Strategies for generating invalid values
_invalid_capacitance = st.integers().filter(lambda x: x not in VALID_CAPACITANCE_RANGE)
_invalid_noise_floor = st.one_of(st.integers(max_value=-1), st.integers(min_value=8))
_invalid_watchdog = st.one_of(st.integers(max_value=-1), st.integers(min_value=16))
_invalid_spike_rejection = st.one_of(st.integers(max_value=-1), st.integers(min_value=16))
_invalid_i2c_address = st.integers().filter(lambda x: x not in VALID_I2C_ADDRESSES)
_invalid_lco_fdiv = st.one_of(st.integers(max_value=-1), st.integers(min_value=4))
_invalid_min_strikes = st.integers().filter(lambda x: x not in VALID_MIN_STRIKES)


@pytest.mark.property
class TestProperty4ValidationRejectsInvalid:
    """Property 4: Input validation rejects invalid values without I2C writes.

    For any integer value outside the valid domain of a parameter, the
    corresponding setter SHALL raise a ValueError whose message contains the
    parameter name, provided value, and valid constraint, AND no
    write_byte_data call SHALL occur on the I2C bus.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**
    """

    @given(value=_invalid_capacitance)
    @settings(max_examples=100)
    def test_rejects_invalid_capacitance(self, value: int) -> None:
        """Invalid capacitance values raise ValueError with parameter name."""
        with pytest.raises(ValueError, match="capacitance"):
            validate_capacitance(value)

    @given(value=_invalid_noise_floor)
    @settings(max_examples=100)
    def test_rejects_invalid_noise_floor_level(self, value: int) -> None:
        """Invalid noise floor level values raise ValueError."""
        with pytest.raises(ValueError, match="noise_floor_level"):
            validate_noise_floor_level(value)

    @given(value=_invalid_watchdog)
    @settings(max_examples=100)
    def test_rejects_invalid_watchdog_threshold(self, value: int) -> None:
        """Invalid watchdog threshold values raise ValueError."""
        with pytest.raises(ValueError, match="watchdog_threshold"):
            validate_watchdog_threshold(value)

    @given(value=_invalid_spike_rejection)
    @settings(max_examples=100)
    def test_rejects_invalid_spike_rejection(self, value: int) -> None:
        """Invalid spike rejection values raise ValueError."""
        with pytest.raises(ValueError, match="spike_rejection"):
            validate_spike_rejection(value)

    @given(value=_invalid_i2c_address)
    @settings(max_examples=100)
    def test_rejects_invalid_i2c_address(self, value: int) -> None:
        """Invalid I2C address values raise ValueError."""
        with pytest.raises(ValueError, match="i2c_address"):
            validate_i2c_address(value)

    @given(value=_invalid_lco_fdiv)
    @settings(max_examples=100)
    def test_rejects_invalid_lco_fdiv(self, value: int) -> None:
        """Invalid LCO fdiv values raise ValueError."""
        with pytest.raises(ValueError, match="lco_fdiv"):
            validate_lco_fdiv(value)

    @given(value=_invalid_min_strikes)
    @settings(max_examples=100)
    def test_rejects_invalid_min_strikes(self, value: int) -> None:
        """Invalid min strikes values raise ValueError."""
        with pytest.raises(ValueError, match="min_strikes"):
            validate_min_strikes(value)

    @given(value=_invalid_noise_floor)
    @settings(max_examples=100)
    def test_no_i2c_write_on_invalid_noise_floor(self, value: int) -> None:
        """No I2C write occurs when noise floor validation fails."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        sensor._bus = mock_bus

        with pytest.raises(ValueError):
            sensor.set_noise_floor_level(value)

        mock_bus.write_byte_data.assert_not_called()

    @given(value=_invalid_watchdog)
    @settings(max_examples=100)
    def test_no_i2c_write_on_invalid_watchdog(self, value: int) -> None:
        """No I2C write occurs when watchdog threshold validation fails."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        sensor._bus = mock_bus

        with pytest.raises(ValueError):
            sensor.set_watchdog_threshold(value)

        mock_bus.write_byte_data.assert_not_called()

    @given(value=_invalid_spike_rejection)
    @settings(max_examples=100)
    def test_no_i2c_write_on_invalid_spike_rejection(self, value: int) -> None:
        """No I2C write occurs when spike rejection validation fails."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        sensor._bus = mock_bus

        with pytest.raises(ValueError):
            sensor.set_spike_rejection(value)

        mock_bus.write_byte_data.assert_not_called()


# ===========================================================================
# Property 5: Input validation accepts all valid values
# ===========================================================================

_valid_capacitance = st.sampled_from(list(VALID_CAPACITANCE_RANGE))
_valid_noise_floor = st.integers(min_value=0, max_value=7)
_valid_watchdog = st.integers(min_value=0, max_value=15)
_valid_spike_rejection_vals = st.integers(min_value=0, max_value=15)
_valid_i2c_addr = st.sampled_from(list(VALID_I2C_ADDRESSES))
_valid_lco_fdiv = st.integers(min_value=0, max_value=3)
_valid_min_strikes_vals = st.sampled_from(list(VALID_MIN_STRIKES))


@pytest.mark.property
class TestProperty5ValidationAcceptsValid:
    """Property 5: Input validation accepts all valid values.

    For any integer value within the valid domain of a parameter, the
    corresponding setter SHALL NOT raise a ValueError.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8**
    """

    @given(value=_valid_capacitance)
    @settings(max_examples=100)
    def test_accepts_valid_capacitance(self, value: int) -> None:
        """Valid capacitance values do not raise ValueError."""
        result = validate_capacitance(value)
        assert result is None

    @given(value=_valid_noise_floor)
    @settings(max_examples=100)
    def test_accepts_valid_noise_floor_level(self, value: int) -> None:
        """Valid noise floor level values do not raise ValueError."""
        result = validate_noise_floor_level(value)
        assert result is None

    @given(value=_valid_watchdog)
    @settings(max_examples=100)
    def test_accepts_valid_watchdog_threshold(self, value: int) -> None:
        """Valid watchdog threshold values do not raise ValueError."""
        result = validate_watchdog_threshold(value)
        assert result is None

    @given(value=_valid_spike_rejection_vals)
    @settings(max_examples=100)
    def test_accepts_valid_spike_rejection(self, value: int) -> None:
        """Valid spike rejection values do not raise ValueError."""
        result = validate_spike_rejection(value)
        assert result is None

    @given(value=_valid_i2c_addr)
    @settings(max_examples=100)
    def test_accepts_valid_i2c_address(self, value: int) -> None:
        """Valid I2C address values do not raise ValueError."""
        result = validate_i2c_address(value)
        assert result is None

    @given(value=_valid_lco_fdiv)
    @settings(max_examples=100)
    def test_accepts_valid_lco_fdiv(self, value: int) -> None:
        """Valid LCO fdiv values do not raise ValueError."""
        result = validate_lco_fdiv(value)
        assert result is None

    @given(value=_valid_min_strikes_vals)
    @settings(max_examples=100)
    def test_accepts_valid_min_strikes(self, value: int) -> None:
        """Valid min strikes values do not raise ValueError."""
        result = validate_min_strikes(value)
        assert result is None


# ===========================================================================
# Property 6: Strike energy assembly and normalization
# ===========================================================================

_lsb_values = st.integers(min_value=0, max_value=255)
_msb_values = st.integers(min_value=0, max_value=255)
_mmsb_values = st.integers(min_value=0, max_value=31)


@pytest.mark.property
class TestProperty6StrikeEnergy:
    """Property 6: Strike energy assembly and normalization.

    For any three byte values (LSB: 0–255, MSB: 0–255, MMSB: 0–31), the raw
    energy SHALL equal (MMSB << 16) | (MSB << 8) | LSB (a 21-bit unsigned
    integer in range 0–2,097,151), and the normalized energy SHALL equal
    raw / 2,097,151 (a float in range [0.0, 1.0]).

    **Validates: Requirements 6.3, 6.4**
    """

    @given(lsb=_lsb_values, msb=_msb_values, mmsb=_mmsb_values)
    @settings(max_examples=100)
    def test_raw_energy_assembly(self, lsb: int, msb: int, mmsb: int) -> None:
        """get_strike_energy_raw assembles (MMSB << 16) | (MSB << 8) | LSB."""
        mock_smbus = MagicMock()

        def read_side_effect(address: int, register: int) -> int:
            if register == REG_ENERGY_LSB:
                return lsb
            elif register == REG_ENERGY_MSB:
                return msb
            elif register == REG_ENERGY_MMSB:
                return mmsb
            return 0x00

        mock_smbus.read_byte_data.side_effect = read_side_effect

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        raw = sensor.get_strike_energy_raw()

        expected_raw = (mmsb << 16) | (msb << 8) | lsb
        assert raw == expected_raw
        assert 0 <= raw <= 2_097_151

    @given(lsb=_lsb_values, msb=_msb_values, mmsb=_mmsb_values)
    @settings(max_examples=100)
    def test_normalized_energy_in_range(self, lsb: int, msb: int, mmsb: int) -> None:
        """get_strike_energy_normalized returns raw / 2,097,151 in [0.0, 1.0]."""
        mock_smbus = MagicMock()

        def read_side_effect(address: int, register: int) -> int:
            if register == REG_ENERGY_LSB:
                return lsb
            elif register == REG_ENERGY_MSB:
                return msb
            elif register == REG_ENERGY_MMSB:
                return mmsb
            return 0x00

        mock_smbus.read_byte_data.side_effect = read_side_effect

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        normalized = sensor.get_strike_energy_normalized()

        expected_raw = (mmsb << 16) | (msb << 8) | lsb
        expected_normalized = expected_raw / 2_097_151
        assert normalized == pytest.approx(expected_normalized)
        assert 0.0 <= normalized <= 1.0


# ===========================================================================
# Property 7: close() is idempotent
# ===========================================================================

_num_close_calls = st.integers(min_value=1, max_value=10)


@pytest.mark.property
class TestProperty7CloseIdempotent:
    """Property 7: close() is idempotent.

    For any number of consecutive close() calls (1 or more) on a sensor
    instance, no call after the first SHALL raise an exception.

    **Validates: Requirements 3.4**
    """

    @given(num_calls=_num_close_calls)
    @settings(max_examples=100)
    def test_close_multiple_times_no_exception(self, num_calls: int) -> None:
        """Calling close() num_calls times raises no exception on any call."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)

        for _ in range(num_calls):
            sensor.close()  # Should not raise


# ===========================================================================
# Property 8: Post-close methods raise RuntimeError
# ===========================================================================

# Public methods that should raise RuntimeError after close()
_post_close_methods = st.sampled_from([
    "set_indoors",
    "set_outdoors",
    "get_noise_floor_level",
    "get_watchdog_threshold",
    "get_spike_rejection",
    "get_interrupt_source",
    "get_lightning_distance_km",
    "get_strike_energy_raw",
    "get_strike_energy_normalized",
    "enable_disturber",
    "disable_disturber",
    "clear_statistics",
])


@pytest.mark.property
class TestProperty8PostCloseRuntimeError:
    """Property 8: Post-close methods raise RuntimeError.

    For any public method (excluding close() and __exit__) called after
    close() has been called, the library SHALL raise a RuntimeError
    indicating the resource has been closed.

    **Validates: Requirements 3.5**
    """

    @given(method_name=_post_close_methods)
    @settings(max_examples=100)
    def test_post_close_method_raises_runtime_error(
        self, method_name: str
    ) -> None:
        """Public methods raise RuntimeError after close()."""
        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor.close()

        method = getattr(sensor, method_name)
        with pytest.raises(RuntimeError, match="closed"):
            method()


# ===========================================================================
# Property 9: Configuration changes emit INFO log
# ===========================================================================

# Strategy that generates (method_name, args) tuples for config setters
_config_operations = st.one_of(
    st.just(("set_indoors", [])),
    st.just(("set_outdoors", [])),
    st.integers(min_value=0, max_value=7).map(lambda v: ("set_noise_floor_level", [v])),
    st.integers(min_value=0, max_value=15).map(lambda v: ("set_watchdog_threshold", [v])),
    st.integers(min_value=0, max_value=15).map(lambda v: ("set_spike_rejection", [v])),
    st.sampled_from(list(VALID_CAPACITANCE_RANGE)).map(lambda v: ("set_tuning_caps", [v])),
    st.integers(min_value=0, max_value=3).map(lambda v: ("set_lco_fdiv", [v])),
    st.sampled_from(list(VALID_MIN_STRIKES)).map(lambda v: ("set_min_strikes", [v])),
    st.just(("enable_disturber", [])),
    st.just(("disable_disturber", [])),
)


@pytest.mark.property
class TestProperty9ConfigLogging:
    """Property 9: Configuration changes emit INFO log.

    For any valid configuration value written via a setter method, the library
    SHALL emit exactly one log record at INFO level containing the new value.

    **Validates: Requirements 9.2**
    """

    @given(operation=_config_operations)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_config_change_emits_info_log(
        self, operation: tuple, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Configuration setter emits an INFO log record."""
        method_name, args = operation

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        mock_bus = MagicMock()
        mock_bus.read_byte_data.return_value = 0x00
        sensor._bus = mock_bus

        method = getattr(sensor, method_name)

        with caplog.at_level(logging.INFO, logger="dfrobot_as3935"):
            caplog.clear()
            method(*args)

        # Assert: at least one INFO record was emitted
        info_records = [
            r for r in caplog.records if r.levelno == logging.INFO
        ]
        assert len(info_records) >= 1, (
            f"Expected at least one INFO log record for {method_name}({args}), "
            f"got {len(info_records)}"
        )


# ===========================================================================
# Property 10: I2C operations emit DEBUG log
# ===========================================================================


@pytest.mark.property
class TestProperty10I2CDebugLogging:
    """Property 10: I2C operations emit DEBUG log.

    For any register read or write operation, the library SHALL emit a log
    record at DEBUG level containing the register address and the value read
    or written.

    **Validates: Requirements 9.3**
    """

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_read_register_emits_debug_log(
        self, register: int, value: int, caplog: pytest.LogCaptureFixture
    ) -> None:
        """_read_register emits a DEBUG log with register address and value."""
        mock_smbus = MagicMock()
        mock_smbus.read_byte_data.return_value = value

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        with caplog.at_level(logging.DEBUG, logger="dfrobot_as3935"):
            caplog.clear()
            sensor._read_register(register)

        debug_records = [
            r for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert len(debug_records) >= 1, (
            f"Expected DEBUG log for read of register 0x{register:02X}, "
            f"value 0x{value:02X}"
        )

        reg_hex = f"0x{register:02X}"
        val_hex = f"0x{value:02X}"
        matching = [
            r for r in debug_records
            if reg_hex in r.getMessage() and val_hex in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"Expected DEBUG log containing register={reg_hex} and "
            f"value={val_hex}, got: {[r.getMessage() for r in debug_records]}"
        )

    @given(register=_valid_registers, value=_byte_values)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_write_register_emits_debug_log(
        self, register: int, value: int, caplog: pytest.LogCaptureFixture
    ) -> None:
        """_write_register emits a DEBUG log with register address and value."""
        mock_smbus = MagicMock()

        sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        sensor._bus = mock_smbus

        with caplog.at_level(logging.DEBUG, logger="dfrobot_as3935"):
            caplog.clear()
            sensor._write_register(register, value)

        debug_records = [
            r for r in caplog.records if r.levelno == logging.DEBUG
        ]
        assert len(debug_records) >= 1, (
            f"Expected DEBUG log for write of register 0x{register:02X}, "
            f"value 0x{value:02X}"
        )

        reg_hex = f"0x{register:02X}"
        val_hex = f"0x{value:02X}"
        matching = [
            r for r in debug_records
            if reg_hex in r.getMessage() and val_hex in r.getMessage()
        ]
        assert len(matching) >= 1, (
            f"Expected DEBUG log containing register={reg_hex} and "
            f"value={val_hex}, got: {[r.getMessage() for r in debug_records]}"
        )
