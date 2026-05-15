"""Shared test configuration and fixtures.

Mocks hardware-dependent modules (smbus2, gpiozero) so tests can run
on any platform without physical hardware.

Provides canonical shared fixtures:
- ``mock_smbus``: Patches ``smbus2.SMBus`` and yields the bus instance mock.
- ``mock_gpio``: Patches ``gpiozero.DigitalInputDevice`` and yields the device mock.
- ``sensor``: Combines both mocks to create a ready-to-use sensor instance.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock hardware-dependent modules before any dfrobot_as3935 imports.
# This allows tests to run on Windows/macOS where fcntl is unavailable.
smbus2_mock = MagicMock()
gpiozero_mock = MagicMock()

sys.modules.setdefault("smbus2", smbus2_mock)
sys.modules.setdefault("gpiozero", gpiozero_mock)
sys.modules.setdefault("fcntl", MagicMock())


@pytest.fixture
def mock_smbus():
    """Patch ``smbus2.SMBus`` in the sensor module.

    Yields the bus *instance* mock (the object returned by ``SMBus(bus_number)``).
    ``read_byte_data`` returns ``0x00`` by default so that sensor initialization
    (reset + verify read) succeeds without additional setup.
    """
    with patch("dfrobot_as3935.sensor.smbus2.SMBus") as smbus_cls:
        bus_instance = MagicMock()
        smbus_cls.return_value = bus_instance
        bus_instance.read_byte_data.return_value = 0x00
        yield bus_instance


@pytest.fixture
def mock_gpio():
    """Patch ``gpiozero.DigitalInputDevice`` in the sensor module.

    Yields the device *instance* mock (the object returned by
    ``DigitalInputDevice(pin, ...)``).
    """
    with patch("dfrobot_as3935.sensor.DigitalInputDevice") as gpio_cls:
        device_instance = MagicMock()
        gpio_cls.return_value = device_instance
        yield device_instance


@pytest.fixture
def sensor(mock_smbus, mock_gpio):
    """Create a ready-to-use ``DFRobot_AS3935`` instance with mocked hardware.

    Uses ``mock_smbus`` and ``mock_gpio`` fixtures so that no physical I2C bus
    or GPIO pin is required. The sensor is initialized with address=0x03,
    bus=1, irq_pin=4.

    Yields the sensor instance. Resets mock call histories after construction
    so tests only observe calls made during the test itself.
    """
    from dfrobot_as3935.sensor import DFRobot_AS3935

    instance = DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
    # Reset call histories so tests see only their own interactions
    mock_smbus.reset_mock()
    mock_gpio.reset_mock()
    yield instance
