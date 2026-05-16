"""Shared test configuration and fixtures.

By default we mock hardware-dependent modules (``smbus2``, ``gpiozero``) so
tests run anywhere without physical hardware. To run true hardware-in-the-loop
tests on a Raspberry Pi with the AS3935 attached, set the environment variable
``AS3935_TEST_REAL_HARDWARE=1`` before invoking pytest. In that mode, the
global module mocks are NOT installed, allowing tests marked ``@pytest.mark.hardware``
to exercise the real device. All other tests may still use the targeted
``mock_smbus``/``mock_gpio`` fixtures as needed.

Provides canonical shared fixtures:
- ``mock_smbus``: Patches ``smbus2.SMBus`` and yields the bus instance mock.
- ``mock_gpio``: Patches ``gpiozero.DigitalInputDevice`` and yields the device mock.
- ``sensor``: Combines both mocks to create a ready-to-use sensor instance.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

HARDWARE_MODE = os.getenv("AS3935_TEST_REAL_HARDWARE", "").lower() in {"1", "true", "yes", "on"}

# Mock hardware-dependent modules before any dfrobot_as3935 imports unless we
# explicitly opt into real-hardware testing.
smbus2_mock = MagicMock()
gpiozero_mock = MagicMock()
mariadb_mock = MagicMock()


class _MariaDBError(Exception):
    """Fake mariadb.Error for testing without the real mariadb C connector."""


mariadb_mock.Error = _MariaDBError

if not HARDWARE_MODE:
    sys.modules.setdefault("smbus2", smbus2_mock)
    sys.modules.setdefault("gpiozero", gpiozero_mock)
sys.modules.setdefault("fcntl", MagicMock())
sys.modules.setdefault("mariadb", mariadb_mock)


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
