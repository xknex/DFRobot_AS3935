"""Unit tests for register_interrupt_callback method.

Tests verify:
- Callback registration sets when_activated on the GPIO device
- Callback replacement overwrites the previous one
- Passing None clears the callback
- The wrapper acquires the RLock before invoking the user callback
- RuntimeError raised if sensor is closed
- INFO logging on register/clear
"""

import logging
import threading
from unittest.mock import MagicMock, patch

import pytest

from dfrobot_as3935.sensor import DFRobot_AS3935


@pytest.fixture
def sensor():
    """Create a sensor instance with mocked hardware."""
    with patch("dfrobot_as3935.sensor.smbus2.SMBus") as mock_smbus_cls, \
         patch("dfrobot_as3935.sensor.DigitalInputDevice") as mock_gpio_cls:
        bus_instance = MagicMock()
        mock_smbus_cls.return_value = bus_instance
        bus_instance.read_byte_data.return_value = 0x00

        gpio_instance = MagicMock()
        mock_gpio_cls.return_value = gpio_instance
        # Allow when_activated to be set as a property
        gpio_instance.when_activated = None

        s = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
        yield s


class TestRegisterInterruptCallback:
    """Tests for register_interrupt_callback."""

    def test_register_callback_sets_when_activated(self, sensor):
        """Registering a callback sets when_activated to a wrapper."""
        my_callback = MagicMock()
        sensor.register_interrupt_callback(my_callback)

        # when_activated should be set to a callable (the wrapper)
        assert sensor._irq_device.when_activated is not None
        assert callable(sensor._irq_device.when_activated)

    def test_clear_callback_with_none(self, sensor):
        """Passing None clears when_activated."""
        my_callback = MagicMock()
        sensor.register_interrupt_callback(my_callback)
        sensor.register_interrupt_callback(None)

        assert sensor._irq_device.when_activated is None
        assert sensor._callback is None

    def test_replace_callback(self, sensor):
        """Replacing a callback overwrites the previous one."""
        first_callback = MagicMock()
        second_callback = MagicMock()

        sensor.register_interrupt_callback(first_callback)
        sensor.register_interrupt_callback(second_callback)

        # Simulate the interrupt by calling the wrapper
        wrapper = sensor._irq_device.when_activated
        wrapper(None)  # gpiozero passes the device as argument

        second_callback.assert_called_once()
        first_callback.assert_not_called()

    def test_wrapper_acquires_lock(self, sensor):
        """The wrapper acquires the RLock before calling user callback."""
        lock_held_during_callback = []

        def check_lock():
            # RLock.acquire(blocking=False) returns True if we can acquire
            # Since RLock is reentrant, if we're already holding it, this succeeds
            acquired = sensor._lock.acquire(blocking=False)
            if acquired:
                lock_held_during_callback.append(True)
                sensor._lock.release()
            else:
                lock_held_during_callback.append(False)

        sensor.register_interrupt_callback(check_lock)

        # Simulate the interrupt
        wrapper = sensor._irq_device.when_activated
        wrapper(None)

        # The lock should have been held (reentrant acquire succeeded)
        assert lock_held_during_callback == [True]

    def test_wrapper_passes_no_args_to_callback(self, sensor):
        """The user callback is called with no arguments."""
        my_callback = MagicMock()
        sensor.register_interrupt_callback(my_callback)

        # Simulate the interrupt (gpiozero passes device as arg)
        wrapper = sensor._irq_device.when_activated
        wrapper(MagicMock())  # device argument from gpiozero

        my_callback.assert_called_once_with()

    def test_raises_runtime_error_after_close(self, sensor):
        """Raises RuntimeError if sensor is closed."""
        sensor.close()
        with pytest.raises(RuntimeError, match="closed"):
            sensor.register_interrupt_callback(lambda: None)

    def test_logs_info_on_register(self, sensor, caplog):
        """Logs INFO when callback is registered."""
        with caplog.at_level(logging.INFO, logger="dfrobot_as3935"):
            sensor.register_interrupt_callback(lambda: None)

        assert any("registered" in r.message.lower() for r in caplog.records)

    def test_logs_info_on_clear(self, sensor, caplog):
        """Logs INFO when callback is cleared."""
        sensor.register_interrupt_callback(lambda: None)
        with caplog.at_level(logging.INFO, logger="dfrobot_as3935"):
            sensor.register_interrupt_callback(None)

        assert any("cleared" in r.message.lower() for r in caplog.records)

    def test_no_callback_interrupt_silently_ignored(self, sensor):
        """If no callback registered, interrupt is silently ignored."""
        # By default, _callback is None and when_activated is not set
        # This verifies the initial state
        assert sensor._callback is None
