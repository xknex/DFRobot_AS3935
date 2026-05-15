"""Named constants for the AS3935 Lightning Sensor IC.

Defines register addresses, bitmasks, configuration values, interrupt source
codes, command bytes, and valid parameter sets per the AS3935 datasheet.
All sensor code should reference these constants instead of numeric literals.
"""

# ---------------------------------------------------------------------------
# Register Addresses
# ---------------------------------------------------------------------------

REG_AFE_GAIN: int = 0x00       # AFE gain and power-down
REG_THRESHOLD: int = 0x01      # Noise floor level and watchdog threshold
REG_LIGHTNING: int = 0x02      # Spike rejection, min strikes, clear stats
REG_INT_MASK_ANT: int = 0x03   # Interrupt source, mask disturber, LCO fdiv
REG_ENERGY_LSB: int = 0x04     # Strike energy LSB
REG_ENERGY_MSB: int = 0x05     # Strike energy MSB
REG_ENERGY_MMSB: int = 0x06    # Strike energy MMSB (bits 4:0)
REG_DISTANCE: int = 0x07       # Distance estimation (bits 5:0)
REG_DISP_TUNE: int = 0x08      # Display/tuning: LCO, SRCO, TRCO, cap
REG_PRESET_DEFAULT: int = 0x3C  # Preset default command register
REG_CALIB_RCO: int = 0x3D      # Calibrate RCO command register

# ---------------------------------------------------------------------------
# Bitmasks
# ---------------------------------------------------------------------------

MASK_PWD: int = 0x01            # Power-down bit (reg 0x00, bit 0)
MASK_AFE_GAIN: int = 0x3E      # AFE gain bits (reg 0x00, bits 5:1)
MASK_NF_LEV: int = 0x70        # Noise floor level (reg 0x01, bits 6:4)
MASK_WDTH: int = 0x0F          # Watchdog threshold (reg 0x01, bits 3:0)
MASK_SREJ: int = 0x0F          # Spike rejection (reg 0x02, bits 3:0)
MASK_MIN_NUM_LIGH: int = 0x30  # Minimum lightning count (reg 0x02, bits 5:4)
MASK_CL_STAT: int = 0x40       # Clear statistics bit (reg 0x02, bit 6)
MASK_INT: int = 0x0F           # Interrupt source (reg 0x03, bits 3:0)
MASK_MASK_DIST: int = 0x20     # Mask disturber (reg 0x03, bit 5)
MASK_LCO_FDIV: int = 0xC0      # LCO frequency division (reg 0x03, bits 7:6)
MASK_ENERGY_MMSB: int = 0x1F   # Energy MMSB (reg 0x06, bits 4:0)
MASK_DISTANCE: int = 0x3F      # Distance (reg 0x07, bits 5:0)
MASK_DISP_LCO: int = 0x80      # Display LCO on IRQ (reg 0x08, bit 7)
MASK_DISP_SRCO: int = 0x40     # Display SRCO on IRQ (reg 0x08, bit 6)
MASK_DISP_TRCO: int = 0x20     # Display TRCO on IRQ (reg 0x08, bit 5)
MASK_DISP_FLAGS: int = 0xE0    # All display bits (reg 0x08, bits 7:5)
MASK_TUN_CAP: int = 0x0F       # Tuning capacitance (reg 0x08, bits 3:0)

# ---------------------------------------------------------------------------
# Configuration Values
# ---------------------------------------------------------------------------

AFE_GAIN_INDOOR: int = 0x24    # Indoor AFE gain setting
AFE_GAIN_OUTDOOR: int = 0x1C   # Outdoor AFE gain setting

# ---------------------------------------------------------------------------
# Interrupt Source Codes
# ---------------------------------------------------------------------------

INT_LIGHTNING: int = 0x08      # Lightning detected
INT_DISTURBER: int = 0x04      # Disturber detected
INT_NOISE: int = 0x01          # Noise level too high

# ---------------------------------------------------------------------------
# Command Bytes
# ---------------------------------------------------------------------------

CMD_PRESET_DEFAULT: int = 0x96  # Written to REG_PRESET_DEFAULT for reset
CMD_CALIB_RCO: int = 0x96      # Written to REG_CALIB_RCO for calibration

# ---------------------------------------------------------------------------
# Valid Parameter Sets
# ---------------------------------------------------------------------------

VALID_I2C_ADDRESSES: tuple[int, ...] = (0x01, 0x02, 0x03)
VALID_MIN_STRIKES: tuple[int, ...] = (1, 5, 9, 16)
VALID_CAPACITANCE_RANGE: range = range(0, 121, 8)  # 0, 8, 16, ..., 120
