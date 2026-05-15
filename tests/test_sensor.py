"""Unit tests for the DFRobot_AS3935 sensor class.

Tests context manager behavior, clear_statistics sequence, IRQ output source,
callback replacement, initialization retry logic, resource cleanup on partial
failure, RLock reentrant acquisition, and nominal/error paths for all public
methods.

Requirements: 13.2, 13.4, 13.5
"""

import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Context Manager Tests
# ---------------------------------------------------------------------------


class TestContextManager:
    """Tests for __enter__ and __exit__ behavior."""

    def test_enter_returns_self(self, sensor):
        """__enter__ returns the sensor instance itself."""
        result = sensor.__enter__()
        assert result is sensor

    def test_exit_does_not_suppress_exceptions(self, sensor):
        """__exit__ returns False, meaning exceptions are not suppressed."""
        result = sensor.__exit__(None, None, None)
        assert result is False

    def test_exit_calls_close(self, sensor, mock_smbus, mock_gpio):
        """__exit__ calls close() to release resources."""
        sensor.__exit__(None, None, None)
        # After exit, calling a method should raise RuntimeError
        with pytest.raises(RuntimeError):
            sensor.set_indoors()

    def test_context_manager_with_statement(self, mock_smbus, mock_gpio):
        """Context manager works correctly with 'with' statement."""
        from dfrobot_as3935.sensor import DFRobot_AS3935

        mock_smbus.reset_mock()
        instance = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        with instance as s:
            assert s is instance
        # After exiting, sensor should be closed
        with pytest.raises(RuntimeError):
            instance.set_indoors()


# ---------------------------------------------------------------------------
# close() Tests
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for close() idempotence and post-close behavior."""

    def test_close_is_idempotent(self, sensor):
        """Multiple close() calls do not raise."""
        sensor.close()
        sensor.close()
        sensor.close()

    def test_post_close_raises_runtime_error(self, sensor):
        """Public methods raise RuntimeError after close()."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_indoors()



# ---------------------------------------------------------------------------
# clear_statistics Tests
# ---------------------------------------------------------------------------


class TestClearStatistics:
    """Tests for the clear_statistics 4-write sequence."""

    def test_clear_statistics_writes_exact_4_sequence(self, sensor, mock_smbus):
        """clear_statistics performs exactly 4 read-modify-write operations.

        The CL_STAT bit (0x40) on register 0x02 must be toggled:
        low, high, low, high.
        """
        # Set up mock to return 0x00 for all reads (no other bits set)
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.clear_statistics()

        # Each _read_modify_write does 1 read + 1 write, so 4 calls = 8 total
        write_calls = mock_smbus.write_byte_data.call_args_list
        read_calls = mock_smbus.read_byte_data.call_args_list

        # Should have exactly 4 reads and 4 writes (one per _read_modify_write)
        assert len(read_calls) == 4
        assert len(write_calls) == 4

        # All reads target register 0x02
        for c in read_calls:
            assert c == call(0x03, 0x02)

        # Writes should alternate: 0x00 (low), 0x40 (high), 0x00 (low), 0x40 (high)
        expected_writes = [
            call(0x03, 0x02, 0x00),  # CL_STAT = 0 (low)
            call(0x03, 0x02, 0x40),  # CL_STAT = 1 (high)
            call(0x03, 0x02, 0x00),  # CL_STAT = 0 (low)
            call(0x03, 0x02, 0x40),  # CL_STAT = 1 (high)
        ]
        assert write_calls == expected_writes

    def test_clear_statistics_preserves_other_bits(self, sensor, mock_smbus):
        """clear_statistics preserves bits outside the CL_STAT mask."""
        # Register 0x02 has SREJ bits (3:0) and MIN_NUM_LIGH (5:4) set
        mock_smbus.read_byte_data.return_value = 0x35  # bits 0,2,4,5 set

        sensor.clear_statistics()

        write_calls = mock_smbus.write_byte_data.call_args_list
        # low: clear bit 6, keep 0x35 → 0x35 & ~0x40 | 0x00 = 0x35
        # high: set bit 6, keep 0x35 → 0x35 & ~0x40 | 0x40 = 0x75
        expected_writes = [
            call(0x03, 0x02, 0x35),  # low: other bits preserved
            call(0x03, 0x02, 0x75),  # high: 0x35 | 0x40
            call(0x03, 0x02, 0x35),  # low: other bits preserved
            call(0x03, 0x02, 0x75),  # high: 0x35 | 0x40
        ]
        assert write_calls == expected_writes



# ---------------------------------------------------------------------------
# set_irq_output_source Tests
# ---------------------------------------------------------------------------


class TestSetIrqOutputSource:
    """Tests for set_irq_output_source, especially the LCO bug fix."""

    def test_source_3_writes_0x80_for_lco(self, sensor, mock_smbus):
        """set_irq_output_source(3) writes 0x80 (LCO bit), not 0x40.

        This verifies the bug fix: the old library incorrectly used 0x40
        for LCO. The correct value per the datasheet is 0x80 (bit 7).
        """
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.set_irq_output_source(3)

        write_calls = mock_smbus.write_byte_data.call_args_list
        # First call clears all display flags (MASK_DISP_FLAGS = 0xE0)
        # Second call sets LCO bit (0x80)
        # Both target register 0x08
        assert any(
            c == call(0x03, 0x08, 0x80) for c in write_calls
        ), f"Expected write of 0x80 to reg 0x08, got: {write_calls}"

    def test_source_0_clears_all_display_bits(self, sensor, mock_smbus):
        """set_irq_output_source(0) clears all display flags."""
        mock_smbus.read_byte_data.return_value = 0xE0  # all display bits set

        sensor.set_irq_output_source(0)

        write_calls = mock_smbus.write_byte_data.call_args_list
        # Should clear bits 7:5, preserving lower bits
        assert call(0x03, 0x08, 0x00) in write_calls

    def test_source_1_writes_trco(self, sensor, mock_smbus):
        """set_irq_output_source(1) writes TRCO bit (0x20)."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.set_irq_output_source(1)

        write_calls = mock_smbus.write_byte_data.call_args_list
        assert any(c == call(0x03, 0x08, 0x20) for c in write_calls)

    def test_source_2_writes_srco(self, sensor, mock_smbus):
        """set_irq_output_source(2) writes SRCO bit (0x40)."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.set_irq_output_source(2)

        write_calls = mock_smbus.write_byte_data.call_args_list
        assert any(c == call(0x03, 0x08, 0x40) for c in write_calls)



# ---------------------------------------------------------------------------
# Callback Replacement Tests
# ---------------------------------------------------------------------------


class TestCallbackReplacement:
    """Tests for interrupt callback registration and replacement."""

    def test_register_callback_sets_when_activated(self, sensor, mock_gpio):
        """Registering a callback sets when_activated on the GPIO device."""
        cb = MagicMock()
        sensor.register_interrupt_callback(cb)
        assert mock_gpio.when_activated is not None

    def test_replacing_callback_overwrites_previous(self, sensor, mock_gpio):
        """Registering a new callback replaces the previous one."""
        cb1 = MagicMock()
        cb2 = MagicMock()

        sensor.register_interrupt_callback(cb1)
        first_handler = mock_gpio.when_activated

        sensor.register_interrupt_callback(cb2)
        second_handler = mock_gpio.when_activated

        # The handler should have been replaced
        assert second_handler is not first_handler

        # Simulate interrupt — only cb2 should be called
        second_handler(None)
        cb2.assert_called_once()
        cb1.assert_not_called()

    def test_clear_callback_with_none(self, sensor, mock_gpio):
        """Passing None clears the callback."""
        cb = MagicMock()
        sensor.register_interrupt_callback(cb)
        sensor.register_interrupt_callback(None)
        assert mock_gpio.when_activated is None

    def test_callback_after_close_raises(self, sensor):
        """Registering a callback after close() raises RuntimeError."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.register_interrupt_callback(lambda: None)



# ---------------------------------------------------------------------------
# Initialization Retry Logic Tests
# ---------------------------------------------------------------------------


class TestInitializationRetry:
    """Tests for _reset_with_retry and initialization failure handling."""

    def test_retry_succeeds_on_second_attempt(self, mock_gpio):
        """Sensor initializes successfully if reset succeeds on retry."""
        with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
            bus_instance = MagicMock()
            smbus_cls.return_value = bus_instance

            # First attempt: write succeeds but read raises OSError
            # Second attempt: everything succeeds
            call_count = [0]

            def side_effect(addr, reg):
                call_count[0] += 1
                if call_count[0] <= 1:
                    raise OSError("I2C timeout")
                return 0x00

            bus_instance.read_byte_data.side_effect = side_effect

            with patch("dfrobot_as3935.sensor.time.sleep"):
                from dfrobot_as3935.sensor import DFRobot_AS3935
                sensor = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
                assert sensor is not None
                sensor.close()

    def test_raises_connection_error_after_3_failures(self, mock_gpio):
        """ConnectionError raised if all 3 retry attempts fail."""
        with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
            bus_instance = MagicMock()
            smbus_cls.return_value = bus_instance
            bus_instance.read_byte_data.side_effect = OSError("I2C timeout")

            with patch("dfrobot_as3935.sensor.time.sleep"):
                from dfrobot_as3935.sensor import DFRobot_AS3935
                with pytest.raises(ConnectionError, match="did not respond"):
                    DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)

    def test_connection_error_includes_address_and_bus(self, mock_gpio):
        """ConnectionError message includes I2C address and bus number."""
        with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
            bus_instance = MagicMock()
            smbus_cls.return_value = bus_instance
            bus_instance.read_byte_data.side_effect = OSError("timeout")

            with patch("dfrobot_as3935.sensor.time.sleep"):
                from dfrobot_as3935.sensor import DFRobot_AS3935
                with pytest.raises(ConnectionError, match="0x03") as exc_info:
                    DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
                assert "bus 1" in str(exc_info.value)



# ---------------------------------------------------------------------------
# Resource Cleanup on Partial Initialization Failure
# ---------------------------------------------------------------------------


class TestResourceCleanupOnFailure:
    """Tests that partially acquired resources are cleaned up on init failure."""

    def test_gpio_failure_closes_i2c_bus(self):
        """If GPIO setup fails, the I2C bus is closed before exception propagates."""
        with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
            bus_instance = MagicMock()
            smbus_cls.return_value = bus_instance

            with patch(
                "dfrobot_as3935.sensor.DigitalInputDevice",
                side_effect=ValueError("Invalid pin"),
            ):
                from dfrobot_as3935.sensor import DFRobot_AS3935
                with pytest.raises(ValueError, match="Invalid pin"):
                    DFRobot_AS3935(address=0x03, bus=1, irq_pin=99)

                # I2C bus should have been closed
                bus_instance.close.assert_called_once()

    def test_reset_failure_closes_both_resources(self):
        """If reset fails, both GPIO and I2C are closed."""
        with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
            bus_instance = MagicMock()
            smbus_cls.return_value = bus_instance
            # Make all reads fail so reset exhausts retries
            bus_instance.read_byte_data.side_effect = OSError("timeout")

            with patch("dfrobot_as3935.sensor.DigitalInputDevice") as gpio_cls:
                gpio_instance = MagicMock()
                gpio_cls.return_value = gpio_instance

                with patch("dfrobot_as3935.sensor.time.sleep"):
                    from dfrobot_as3935.sensor import DFRobot_AS3935
                    with pytest.raises(ConnectionError):
                        DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)

                    # Both resources should be cleaned up
                    gpio_instance.close.assert_called_once()
                    bus_instance.close.assert_called_once()

    def test_i2c_bus_open_failure_raises_oserror(self):
        """OSError raised if I2C bus cannot be opened."""
        with patch(
            "dfrobot_as3935.sensor.smbus2.SMBus",
            side_effect=OSError("No such device"),
        ):
            from dfrobot_as3935.sensor import DFRobot_AS3935
            with pytest.raises(OSError, match="Failed to open I2C bus"):
                DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)



# ---------------------------------------------------------------------------
# RLock Reentrant Acquisition Tests
# ---------------------------------------------------------------------------


class TestRLockReentrant:
    """Tests that the RLock allows reentrant acquisition without deadlock."""

    def test_reentrant_lock_no_deadlock(self, sensor, mock_smbus):
        """RLock allows the same thread to acquire it multiple times.

        This simulates a scenario where a method that holds the lock
        calls another method that also acquires the lock (reentrant).
        """
        mock_smbus.read_byte_data.return_value = 0x00

        # Acquire the lock manually, then call a method that also acquires it
        with sensor._lock:
            # This should NOT deadlock because RLock is reentrant
            result = sensor.get_noise_floor_level()
            assert result == 0

    def test_lock_prevents_concurrent_corruption(self, sensor, mock_smbus):
        """Verify that the lock serializes concurrent access."""
        mock_smbus.read_byte_data.return_value = 0x00
        results = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    sensor.get_noise_floor_level()
                results.append("ok")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert len(results) == 4



# ---------------------------------------------------------------------------
# Public Method Nominal Path Tests
# ---------------------------------------------------------------------------


class TestPublicMethodsNominal:
    """Tests for each public method's nominal (happy) path."""

    def test_set_indoors(self, sensor, mock_smbus):
        """set_indoors writes AFE_GAIN_INDOOR (0x24) to register 0x00."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_indoors()
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x00, 0x24)

    def test_set_outdoors(self, sensor, mock_smbus):
        """set_outdoors writes AFE_GAIN_OUTDOOR (0x1C) to register 0x00."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_outdoors()
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x00, 0x1C)

    def test_set_noise_floor_level(self, sensor, mock_smbus):
        """set_noise_floor_level(5) writes shifted value to register 0x01."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_noise_floor_level(5)
        # 5 << 4 = 0x50, masked with 0x70 = 0x50
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x01, 0x50)

    def test_get_noise_floor_level(self, sensor, mock_smbus):
        """get_noise_floor_level returns correct shifted value."""
        mock_smbus.read_byte_data.return_value = 0x50  # level 5 in bits 6:4
        result = sensor.get_noise_floor_level()
        assert result == 5

    def test_set_watchdog_threshold(self, sensor, mock_smbus):
        """set_watchdog_threshold(10) writes to register 0x01 bits 3:0."""
        mock_smbus.read_byte_data.return_value = 0x50  # NF_LEV bits set
        sensor.set_watchdog_threshold(10)
        # Preserve NF_LEV (0x50), set WDTH to 10 (0x0A)
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x01, 0x5A)

    def test_get_watchdog_threshold(self, sensor, mock_smbus):
        """get_watchdog_threshold returns bits 3:0 of register 0x01."""
        mock_smbus.read_byte_data.return_value = 0x5A  # WDTH=10
        result = sensor.get_watchdog_threshold()
        assert result == 10

    def test_set_spike_rejection(self, sensor, mock_smbus):
        """set_spike_rejection(7) writes to register 0x02 bits 3:0."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_spike_rejection(7)
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x02, 0x07)

    def test_get_spike_rejection(self, sensor, mock_smbus):
        """get_spike_rejection returns bits 3:0 of register 0x02."""
        mock_smbus.read_byte_data.return_value = 0x47  # CL_STAT + SREJ=7
        result = sensor.get_spike_rejection()
        assert result == 7

    def test_set_tuning_caps(self, sensor, mock_smbus):
        """set_tuning_caps(56) writes 56>>3=7 to register 0x08 bits 3:0."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_tuning_caps(56)
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x08, 0x07)

    def test_set_min_strikes(self, sensor, mock_smbus):
        """set_min_strikes(9) writes 0x20 to register 0x02 bits 5:4."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_min_strikes(9)
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x02, 0x20)

    def test_set_lco_fdiv(self, sensor, mock_smbus):
        """set_lco_fdiv(2) writes 2<<6=0x80 to register 0x03 bits 7:6."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.set_lco_fdiv(2)
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x03, 0x80)

    def test_enable_disturber(self, sensor, mock_smbus):
        """enable_disturber clears MASK_DIST bit (0x20) in register 0x03."""
        mock_smbus.read_byte_data.return_value = 0x20  # disturber masked
        sensor.enable_disturber()
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x03, 0x00)

    def test_disable_disturber(self, sensor, mock_smbus):
        """disable_disturber sets MASK_DIST bit (0x20) in register 0x03."""
        mock_smbus.read_byte_data.return_value = 0x00
        sensor.disable_disturber()
        mock_smbus.write_byte_data.assert_called_with(0x03, 0x03, 0x20)

    def test_get_interrupt_source(self, sensor, mock_smbus):
        """get_interrupt_source returns masked bits 3:0 of register 0x03."""
        mock_smbus.read_byte_data.return_value = 0x08  # lightning
        with patch("dfrobot_as3935.sensor.time.sleep"):
            result = sensor.get_interrupt_source()
        assert result == 0x08

    def test_get_lightning_distance_km(self, sensor, mock_smbus):
        """get_lightning_distance_km returns bits 5:0 of register 0x07."""
        mock_smbus.read_byte_data.return_value = 0x28  # distance = 40
        result = sensor.get_lightning_distance_km()
        assert result == 40

    def test_get_strike_energy_raw(self, sensor, mock_smbus):
        """get_strike_energy_raw combines 3 registers into 21-bit value."""
        # LSB=0xAB, MSB=0xCD, MMSB=0x0F (only bits 4:0)
        mock_smbus.read_byte_data.side_effect = [0xAB, 0xCD, 0x0F]
        result = sensor.get_strike_energy_raw()
        expected = (0x0F << 16) | (0xCD << 8) | 0xAB
        assert result == expected

    def test_get_strike_energy_normalized(self, sensor, mock_smbus):
        """get_strike_energy_normalized returns value in [0.0, 1.0]."""
        # Max value: LSB=0xFF, MSB=0xFF, MMSB=0x1F
        mock_smbus.read_byte_data.side_effect = [0xFF, 0xFF, 0x1F]
        result = sensor.get_strike_energy_normalized()
        assert result == pytest.approx(1.0)

    def test_get_strike_energy_normalized_zero(self, sensor, mock_smbus):
        """get_strike_energy_normalized returns 0.0 for zero energy."""
        mock_smbus.read_byte_data.side_effect = [0x00, 0x00, 0x00]
        result = sensor.get_strike_energy_normalized()
        assert result == 0.0



# ---------------------------------------------------------------------------
# Public Method Error Path Tests
# ---------------------------------------------------------------------------


class TestPublicMethodsError:
    """Tests for each public method's error path."""

    def test_set_indoors_after_close(self, sensor):
        """set_indoors raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_indoors()

    def test_set_outdoors_after_close(self, sensor):
        """set_outdoors raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_outdoors()

    def test_set_noise_floor_level_invalid(self, sensor):
        """set_noise_floor_level raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            sensor.set_noise_floor_level(8)

    def test_set_noise_floor_level_after_close(self, sensor):
        """set_noise_floor_level raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_noise_floor_level(3)

    def test_get_noise_floor_level_after_close(self, sensor):
        """get_noise_floor_level raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_noise_floor_level()

    def test_set_watchdog_threshold_invalid(self, sensor):
        """set_watchdog_threshold raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            sensor.set_watchdog_threshold(16)

    def test_set_watchdog_threshold_after_close(self, sensor):
        """set_watchdog_threshold raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_watchdog_threshold(5)

    def test_get_watchdog_threshold_after_close(self, sensor):
        """get_watchdog_threshold raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_watchdog_threshold()

    def test_set_spike_rejection_invalid(self, sensor):
        """set_spike_rejection raises ValueError for invalid input."""
        with pytest.raises(ValueError):
            sensor.set_spike_rejection(16)

    def test_set_spike_rejection_after_close(self, sensor):
        """set_spike_rejection raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_spike_rejection(5)

    def test_get_spike_rejection_after_close(self, sensor):
        """get_spike_rejection raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_spike_rejection()

    def test_set_tuning_caps_invalid(self, sensor):
        """set_tuning_caps raises ValueError for non-multiple-of-8."""
        with pytest.raises(ValueError):
            sensor.set_tuning_caps(7)

    def test_set_tuning_caps_after_close(self, sensor):
        """set_tuning_caps raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_tuning_caps(8)

    def test_set_min_strikes_invalid(self, sensor):
        """set_min_strikes raises ValueError for invalid value."""
        with pytest.raises(ValueError):
            sensor.set_min_strikes(3)

    def test_set_min_strikes_after_close(self, sensor):
        """set_min_strikes raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_min_strikes(1)

    def test_set_lco_fdiv_invalid(self, sensor):
        """set_lco_fdiv raises ValueError for out-of-range value."""
        with pytest.raises(ValueError):
            sensor.set_lco_fdiv(4)

    def test_set_lco_fdiv_after_close(self, sensor):
        """set_lco_fdiv raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_lco_fdiv(1)

    def test_set_irq_output_source_after_close(self, sensor):
        """set_irq_output_source raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.set_irq_output_source(0)

    def test_enable_disturber_after_close(self, sensor):
        """enable_disturber raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.enable_disturber()

    def test_disable_disturber_after_close(self, sensor):
        """disable_disturber raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.disable_disturber()

    def test_clear_statistics_after_close(self, sensor):
        """clear_statistics raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.clear_statistics()

    def test_get_interrupt_source_after_close(self, sensor):
        """get_interrupt_source raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_interrupt_source()

    def test_get_lightning_distance_km_after_close(self, sensor):
        """get_lightning_distance_km raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_lightning_distance_km()

    def test_get_strike_energy_raw_after_close(self, sensor):
        """get_strike_energy_raw raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_strike_energy_raw()

    def test_get_strike_energy_normalized_after_close(self, sensor):
        """get_strike_energy_normalized raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.get_strike_energy_normalized()

    def test_i2c_read_error_wraps_oserror(self, sensor, mock_smbus):
        """I2C read failure raises OSError with diagnostic context."""
        mock_smbus.read_byte_data.side_effect = OSError("bus error")
        with pytest.raises(OSError, match="register=0x01"):
            sensor.get_noise_floor_level()

    def test_i2c_write_error_wraps_oserror(self, sensor, mock_smbus):
        """I2C write failure raises OSError with diagnostic context."""
        mock_smbus.read_byte_data.return_value = 0x00
        mock_smbus.write_byte_data.side_effect = OSError("bus error")
        with pytest.raises(OSError, match="device=0x03"):
            sensor.set_indoors()


# ---------------------------------------------------------------------------
# configure() Convenience Method Tests
# ---------------------------------------------------------------------------


class TestConfigure:
    """Tests for the configure() convenience method."""

    def test_defaults_calls_indoors_disturber_caps96(self, sensor, mock_smbus):
        """configure() with defaults calls set_indoors, enable_disturber, set_tuning_caps(96)."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.configure()

        write_calls = mock_smbus.write_byte_data.call_args_list
        # set_indoors writes AFE_GAIN_INDOOR (0x24) to register 0x00
        assert call(0x03, 0x00, 0x24) in write_calls
        # enable_disturber clears MASK_DIST (0x20) in register 0x03
        assert call(0x03, 0x03, 0x00) in write_calls
        # set_tuning_caps(96): 96 >> 3 = 12 (0x0C) to register 0x08
        assert call(0x03, 0x08, 0x0C) in write_calls

    def test_indoor_false_calls_set_outdoors(self, sensor, mock_smbus):
        """configure(indoor=False) calls set_outdoors."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.configure(indoor=False)

        write_calls = mock_smbus.write_byte_data.call_args_list
        # set_outdoors writes AFE_GAIN_OUTDOOR (0x1C) to register 0x00
        assert call(0x03, 0x00, 0x1C) in write_calls

    def test_disturber_false_calls_disable_disturber(self, sensor, mock_smbus):
        """configure(disturber=False) calls disable_disturber."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.configure(disturber=False)

        write_calls = mock_smbus.write_byte_data.call_args_list
        # disable_disturber sets MASK_DIST (0x20) in register 0x03
        assert call(0x03, 0x03, 0x20) in write_calls

    def test_capacitance_48_passes_to_set_tuning_caps(self, sensor, mock_smbus):
        """configure(capacitance=48) passes 48 to set_tuning_caps."""
        mock_smbus.read_byte_data.return_value = 0x00

        sensor.configure(capacitance=48)

        write_calls = mock_smbus.write_byte_data.call_args_list
        # set_tuning_caps(48): 48 >> 3 = 6 (0x06) to register 0x08
        assert call(0x03, 0x08, 0x06) in write_calls

    def test_invalid_capacitance_raises_value_error(self, sensor):
        """configure() raises ValueError for invalid capacitance."""
        with pytest.raises(ValueError):
            sensor.configure(capacitance=7)

    def test_invalid_capacitance_out_of_range(self, sensor):
        """configure() raises ValueError for capacitance > 120."""
        with pytest.raises(ValueError):
            sensor.configure(capacitance=128)

    def test_after_close_raises_runtime_error(self, sensor):
        """configure() raises RuntimeError after close."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.configure()
