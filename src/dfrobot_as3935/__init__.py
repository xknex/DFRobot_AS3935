"""DFRobot AS3935 Lightning Sensor driver for Raspberry Pi.

A modern Python library for communicating with the AS3935 lightning sensor IC
over I2C on Raspberry Pi (Zero 2W and compatible boards). Supports interrupt-
based detection of lightning strikes, disturbers, and noise events via GPIO.

Hardware:
    The AS3935 is a programmable lightning sensor IC that detects lightning
    activity up to 40 km away. It communicates over I2C (addresses 0x01–0x03)
    and signals events via a rising edge on the IRQ pin.

Usage::

    from dfrobot_as3935 import DFRobot_AS3935, INT_LIGHTNING

    with DFRobot_AS3935(address=0x03, bus=1, irq_pin=4) as sensor:
        sensor.set_indoors()
        sensor.set_noise_floor_level(2)

        def on_interrupt():
            source = sensor.get_interrupt_source()
            if source == INT_LIGHTNING:
                distance = sensor.get_lightning_distance_km()
                print(f"Lightning detected {distance} km away")

        sensor.register_interrupt_callback(on_interrupt)
"""

from .constants import (
    # Register Addresses
    REG_AFE_GAIN,
    REG_THRESHOLD,
    REG_LIGHTNING,
    REG_INT_MASK_ANT,
    REG_ENERGY_LSB,
    REG_ENERGY_MSB,
    REG_ENERGY_MMSB,
    REG_DISTANCE,
    REG_DISP_TUNE,
    REG_PRESET_DEFAULT,
    REG_CALIB_RCO,
    # Bitmasks
    MASK_PWD,
    MASK_AFE_GAIN,
    MASK_NF_LEV,
    MASK_WDTH,
    MASK_SREJ,
    MASK_MIN_NUM_LIGH,
    MASK_CL_STAT,
    MASK_INT,
    MASK_MASK_DIST,
    MASK_LCO_FDIV,
    MASK_ENERGY_MMSB,
    MASK_DISTANCE,
    MASK_DISP_LCO,
    MASK_DISP_SRCO,
    MASK_DISP_TRCO,
    MASK_DISP_FLAGS,
    MASK_TUN_CAP,
    # Configuration Values
    AFE_GAIN_INDOOR,
    AFE_GAIN_OUTDOOR,
    # Interrupt Source Codes
    INT_LIGHTNING,
    INT_DISTURBER,
    INT_NOISE,
    # Command Bytes
    CMD_PRESET_DEFAULT,
    CMD_CALIB_RCO,
    # Valid Parameter Sets
    VALID_I2C_ADDRESSES,
    VALID_MIN_STRIKES,
    VALID_CAPACITANCE_RANGE,
)
from .sensor import DFRobot_AS3935

__all__ = [
    # Main sensor class
    "DFRobot_AS3935",
    # Register Addresses
    "REG_AFE_GAIN",
    "REG_THRESHOLD",
    "REG_LIGHTNING",
    "REG_INT_MASK_ANT",
    "REG_ENERGY_LSB",
    "REG_ENERGY_MSB",
    "REG_ENERGY_MMSB",
    "REG_DISTANCE",
    "REG_DISP_TUNE",
    "REG_PRESET_DEFAULT",
    "REG_CALIB_RCO",
    # Bitmasks
    "MASK_PWD",
    "MASK_AFE_GAIN",
    "MASK_NF_LEV",
    "MASK_WDTH",
    "MASK_SREJ",
    "MASK_MIN_NUM_LIGH",
    "MASK_CL_STAT",
    "MASK_INT",
    "MASK_MASK_DIST",
    "MASK_LCO_FDIV",
    "MASK_ENERGY_MMSB",
    "MASK_DISTANCE",
    "MASK_DISP_LCO",
    "MASK_DISP_SRCO",
    "MASK_DISP_TRCO",
    "MASK_DISP_FLAGS",
    "MASK_TUN_CAP",
    # Configuration Values
    "AFE_GAIN_INDOOR",
    "AFE_GAIN_OUTDOOR",
    # Interrupt Source Codes
    "INT_LIGHTNING",
    "INT_DISTURBER",
    "INT_NOISE",
    # Command Bytes
    "CMD_PRESET_DEFAULT",
    "CMD_CALIB_RCO",
    # Valid Parameter Sets
    "VALID_I2C_ADDRESSES",
    "VALID_MIN_STRIKES",
    "VALID_CAPACITANCE_RANGE",
]
