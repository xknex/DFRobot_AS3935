"""Smoke tests for constant definitions and package structure.

Verifies that all named constants are defined, importable, and have correct
values per the AS3935 datasheet. Also checks __all__ exports and ensures
no print() statements exist in library source code.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

import ast
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Test: Register address constants exist and have correct values (Req 4.1)
# ---------------------------------------------------------------------------

class TestRegisterAddresses:
    """Verify all register address constants are defined with correct values."""

    def test_reg_afe_gain(self):
        from dfrobot_as3935.constants import REG_AFE_GAIN
        assert REG_AFE_GAIN == 0x00

    def test_reg_threshold(self):
        from dfrobot_as3935.constants import REG_THRESHOLD
        assert REG_THRESHOLD == 0x01

    def test_reg_lightning(self):
        from dfrobot_as3935.constants import REG_LIGHTNING
        assert REG_LIGHTNING == 0x02

    def test_reg_int_mask_ant(self):
        from dfrobot_as3935.constants import REG_INT_MASK_ANT
        assert REG_INT_MASK_ANT == 0x03

    def test_reg_energy_lsb(self):
        from dfrobot_as3935.constants import REG_ENERGY_LSB
        assert REG_ENERGY_LSB == 0x04

    def test_reg_energy_msb(self):
        from dfrobot_as3935.constants import REG_ENERGY_MSB
        assert REG_ENERGY_MSB == 0x05

    def test_reg_energy_mmsb(self):
        from dfrobot_as3935.constants import REG_ENERGY_MMSB
        assert REG_ENERGY_MMSB == 0x06

    def test_reg_distance(self):
        from dfrobot_as3935.constants import REG_DISTANCE
        assert REG_DISTANCE == 0x07

    def test_reg_disp_tune(self):
        from dfrobot_as3935.constants import REG_DISP_TUNE
        assert REG_DISP_TUNE == 0x08

    def test_reg_preset_default(self):
        from dfrobot_as3935.constants import REG_PRESET_DEFAULT
        assert REG_PRESET_DEFAULT == 0x3C

    def test_reg_calib_rco(self):
        from dfrobot_as3935.constants import REG_CALIB_RCO
        assert REG_CALIB_RCO == 0x3D


# ---------------------------------------------------------------------------
# Test: Bitmask constants exist and have correct values (Req 4.2)
# ---------------------------------------------------------------------------

class TestBitmasks:
    """Verify all bitmask constants are defined with correct values."""

    def test_mask_pwd(self):
        from dfrobot_as3935.constants import MASK_PWD
        assert MASK_PWD == 0x01

    def test_mask_afe_gain(self):
        from dfrobot_as3935.constants import MASK_AFE_GAIN
        assert MASK_AFE_GAIN == 0x3E

    def test_mask_nf_lev(self):
        from dfrobot_as3935.constants import MASK_NF_LEV
        assert MASK_NF_LEV == 0x70

    def test_mask_wdth(self):
        from dfrobot_as3935.constants import MASK_WDTH
        assert MASK_WDTH == 0x0F

    def test_mask_srej(self):
        from dfrobot_as3935.constants import MASK_SREJ
        assert MASK_SREJ == 0x0F

    def test_mask_min_num_ligh(self):
        from dfrobot_as3935.constants import MASK_MIN_NUM_LIGH
        assert MASK_MIN_NUM_LIGH == 0x30

    def test_mask_cl_stat(self):
        from dfrobot_as3935.constants import MASK_CL_STAT
        assert MASK_CL_STAT == 0x40

    def test_mask_int(self):
        from dfrobot_as3935.constants import MASK_INT
        assert MASK_INT == 0x0F

    def test_mask_mask_dist(self):
        from dfrobot_as3935.constants import MASK_MASK_DIST
        assert MASK_MASK_DIST == 0x20

    def test_mask_lco_fdiv(self):
        from dfrobot_as3935.constants import MASK_LCO_FDIV
        assert MASK_LCO_FDIV == 0xC0

    def test_mask_energy_mmsb(self):
        from dfrobot_as3935.constants import MASK_ENERGY_MMSB
        assert MASK_ENERGY_MMSB == 0x1F

    def test_mask_distance(self):
        from dfrobot_as3935.constants import MASK_DISTANCE
        assert MASK_DISTANCE == 0x3F

    def test_mask_disp_lco(self):
        from dfrobot_as3935.constants import MASK_DISP_LCO
        assert MASK_DISP_LCO == 0x80

    def test_mask_disp_srco(self):
        from dfrobot_as3935.constants import MASK_DISP_SRCO
        assert MASK_DISP_SRCO == 0x40

    def test_mask_disp_trco(self):
        from dfrobot_as3935.constants import MASK_DISP_TRCO
        assert MASK_DISP_TRCO == 0x20

    def test_mask_disp_flags(self):
        from dfrobot_as3935.constants import MASK_DISP_FLAGS
        assert MASK_DISP_FLAGS == 0xE0

    def test_mask_tun_cap(self):
        from dfrobot_as3935.constants import MASK_TUN_CAP
        assert MASK_TUN_CAP == 0x0F


# ---------------------------------------------------------------------------
# Test: Configuration values (Req 4.3)
# ---------------------------------------------------------------------------

class TestConfigurationValues:
    """Verify AFE gain configuration constants match datasheet."""

    def test_afe_gain_indoor(self):
        from dfrobot_as3935.constants import AFE_GAIN_INDOOR
        assert AFE_GAIN_INDOOR == 0x24

    def test_afe_gain_outdoor(self):
        from dfrobot_as3935.constants import AFE_GAIN_OUTDOOR
        assert AFE_GAIN_OUTDOOR == 0x1C


# ---------------------------------------------------------------------------
# Test: Interrupt source codes (Req 4.4)
# ---------------------------------------------------------------------------

class TestInterruptCodes:
    """Verify interrupt source code constants match datasheet."""

    def test_int_lightning(self):
        from dfrobot_as3935.constants import INT_LIGHTNING
        assert INT_LIGHTNING == 0x08

    def test_int_disturber(self):
        from dfrobot_as3935.constants import INT_DISTURBER
        assert INT_DISTURBER == 0x04

    def test_int_noise(self):
        from dfrobot_as3935.constants import INT_NOISE
        assert INT_NOISE == 0x01


# ---------------------------------------------------------------------------
# Test: Command bytes (Req 4.5)
# ---------------------------------------------------------------------------

class TestCommandBytes:
    """Verify command byte constants match datasheet."""

    def test_cmd_preset_default(self):
        from dfrobot_as3935.constants import CMD_PRESET_DEFAULT
        assert CMD_PRESET_DEFAULT == 0x96

    def test_cmd_calib_rco(self):
        from dfrobot_as3935.constants import CMD_CALIB_RCO
        assert CMD_CALIB_RCO == 0x96


# ---------------------------------------------------------------------------
# Test: Valid parameter sets (Req 4.1, 4.2)
# ---------------------------------------------------------------------------

class TestValidParameterSets:
    """Verify valid parameter set constants are defined correctly."""

    def test_valid_i2c_addresses(self):
        from dfrobot_as3935.constants import VALID_I2C_ADDRESSES
        assert VALID_I2C_ADDRESSES == (0x01, 0x02, 0x03)

    def test_valid_min_strikes(self):
        from dfrobot_as3935.constants import VALID_MIN_STRIKES
        assert VALID_MIN_STRIKES == (1, 5, 9, 16)

    def test_valid_capacitance_range(self):
        from dfrobot_as3935.constants import VALID_CAPACITANCE_RANGE
        expected = list(range(0, 121, 8))
        assert list(VALID_CAPACITANCE_RANGE) == expected


# ---------------------------------------------------------------------------
# Test: __all__ exports expected names (Req 8.2)
# ---------------------------------------------------------------------------

class TestAllExports:
    """Verify __init__.py __all__ exports the main class and all constants."""

    def test_all_contains_main_class(self):
        import dfrobot_as3935
        assert "DFRobot_AS3935" in dfrobot_as3935.__all__

    def test_all_contains_register_addresses(self):
        import dfrobot_as3935
        register_names = [
            "REG_AFE_GAIN", "REG_THRESHOLD", "REG_LIGHTNING",
            "REG_INT_MASK_ANT", "REG_ENERGY_LSB", "REG_ENERGY_MSB",
            "REG_ENERGY_MMSB", "REG_DISTANCE", "REG_DISP_TUNE",
            "REG_PRESET_DEFAULT", "REG_CALIB_RCO",
        ]
        for name in register_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_contains_bitmasks(self):
        import dfrobot_as3935
        mask_names = [
            "MASK_PWD", "MASK_AFE_GAIN", "MASK_NF_LEV", "MASK_WDTH",
            "MASK_SREJ", "MASK_MIN_NUM_LIGH", "MASK_CL_STAT", "MASK_INT",
            "MASK_MASK_DIST", "MASK_LCO_FDIV", "MASK_ENERGY_MMSB",
            "MASK_DISTANCE", "MASK_DISP_LCO", "MASK_DISP_SRCO",
            "MASK_DISP_TRCO", "MASK_DISP_FLAGS", "MASK_TUN_CAP",
        ]
        for name in mask_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_contains_config_values(self):
        import dfrobot_as3935
        config_names = ["AFE_GAIN_INDOOR", "AFE_GAIN_OUTDOOR"]
        for name in config_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_contains_interrupt_codes(self):
        import dfrobot_as3935
        int_names = ["INT_LIGHTNING", "INT_DISTURBER", "INT_NOISE"]
        for name in int_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_contains_command_bytes(self):
        import dfrobot_as3935
        cmd_names = ["CMD_PRESET_DEFAULT", "CMD_CALIB_RCO"]
        for name in cmd_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_contains_valid_parameter_sets(self):
        import dfrobot_as3935
        param_names = [
            "VALID_I2C_ADDRESSES", "VALID_MIN_STRIKES",
            "VALID_CAPACITANCE_RANGE",
        ]
        for name in param_names:
            assert name in dfrobot_as3935.__all__, f"{name} missing from __all__"

    def test_all_exports_are_importable(self):
        """Every name in __all__ should be an accessible attribute."""
        import dfrobot_as3935
        for name in dfrobot_as3935.__all__:
            assert hasattr(dfrobot_as3935, name), (
                f"{name} listed in __all__ but not importable"
            )


# ---------------------------------------------------------------------------
# Test: No print() statements in library source code (Req 9.5)
# ---------------------------------------------------------------------------

class TestNoPrintStatements:
    """Verify library source files contain no print() calls."""

    @staticmethod
    def _get_source_dir() -> Path:
        """Return the path to the library source directory."""
        return Path(__file__).resolve().parent.parent / "src" / "dfrobot_as3935"

    @staticmethod
    def _has_print_calls(filepath: Path) -> list[int]:
        """Parse a Python file and return line numbers with print() calls."""
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        lines_with_print: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "print":
                    lines_with_print.append(node.lineno)
        return lines_with_print

    def test_no_print_in_sensor(self):
        source_dir = self._get_source_dir()
        filepath = source_dir / "sensor.py"
        if filepath.exists():
            lines = self._has_print_calls(filepath)
            assert lines == [], (
                f"sensor.py contains print() on lines: {lines}"
            )

    def test_no_print_in_constants(self):
        source_dir = self._get_source_dir()
        filepath = source_dir / "constants.py"
        if filepath.exists():
            lines = self._has_print_calls(filepath)
            assert lines == [], (
                f"constants.py contains print() on lines: {lines}"
            )

    def test_no_print_in_validators(self):
        source_dir = self._get_source_dir()
        filepath = source_dir / "validators.py"
        if filepath.exists():
            lines = self._has_print_calls(filepath)
            assert lines == [], (
                f"validators.py contains print() on lines: {lines}"
            )
