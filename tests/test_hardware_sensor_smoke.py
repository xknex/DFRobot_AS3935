"""Opt-in hardware smoke test for AS3935 on Raspberry Pi.

Run only when AS3935_TEST_REAL_HARDWARE=1 is set in the environment.
Allows overriding bus/address/IRQ via env vars:
- AS3935_I2C_ADDRESS (default: 0x03)
- AS3935_I2C_BUS (default: 1)
- AS3935_IRQ_PIN (default: 4)
"""
from __future__ import annotations

import os
import pytest

HARDWARE_MODE = os.getenv("AS3935_TEST_REAL_HARDWARE", "").lower() in {"1", "true", "yes", "on"}

pytestmark = pytest.mark.hardware


@pytest.mark.skipif(not HARDWARE_MODE, reason="hardware test requires AS3935_TEST_REAL_HARDWARE=1")
def test_sensor_basic_register_access() -> None:
    from dfrobot_as3935.sensor import DFRobot_AS3935

    # Parse configuration from environment with sensible defaults
    addr_str = os.getenv("AS3935_I2C_ADDRESS", "0x03")
    address = int(addr_str, 0)
    bus = int(os.getenv("AS3935_I2C_BUS", "1"))
    irq = int(os.getenv("AS3935_IRQ_PIN", "4"))

    # Basic open → read → close cycle should succeed on target hardware
    with DFRobot_AS3935(address=address, bus=bus, irq_pin=irq) as sensor:
        # A simple read that exercises I2C: fetch the current noise-floor level
        level = sensor.get_noise_floor_level()
        assert 0 <= level <= 7
