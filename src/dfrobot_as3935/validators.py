"""Input validation functions for AS3935 Lightning Sensor parameters.

Each validator checks that a given value meets the constraints defined by the
AS3935 datasheet. Invalid values raise ``ValueError`` with a message containing
the parameter name, the provided value, and the valid constraint.
"""

from dfrobot_as3935.constants import (
    VALID_CAPACITANCE_RANGE,
    VALID_I2C_ADDRESSES,
    VALID_MIN_STRIKES,
)


def validate_capacitance(value: int) -> None:
    """Validate tuning capacitance value.

    Args:
        value: Capacitance value to validate. Must be an integer,
            a multiple of 8, and in the range 0–120.

    Raises:
        ValueError: If value is not an integer, not a multiple of 8,
            or outside the range 0–120.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"capacitance must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value not in VALID_CAPACITANCE_RANGE:
        raise ValueError(
            f"capacitance must be a multiple of 8 in range 0–120, got {value}"
        )


def validate_noise_floor_level(value: int) -> None:
    """Validate noise floor level value.

    Args:
        value: Noise floor level to validate. Must be an integer
            in the range 0–7.

    Raises:
        ValueError: If value is not an integer or outside the range 0–7.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"noise_floor_level must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value < 0 or value > 7:
        raise ValueError(
            f"noise_floor_level must be in range 0–7, got {value}"
        )


def validate_watchdog_threshold(value: int) -> None:
    """Validate watchdog threshold value.

    Args:
        value: Watchdog threshold to validate. Must be an integer
            in the range 0–15.

    Raises:
        ValueError: If value is not an integer or outside the range 0–15.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"watchdog_threshold must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value < 0 or value > 15:
        raise ValueError(
            f"watchdog_threshold must be in range 0–15, got {value}"
        )


def validate_spike_rejection(value: int) -> None:
    """Validate spike rejection value.

    Args:
        value: Spike rejection value to validate. Must be an integer
            in the range 0–15.

    Raises:
        ValueError: If value is not an integer or outside the range 0–15.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"spike_rejection must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value < 0 or value > 15:
        raise ValueError(
            f"spike_rejection must be in range 0–15, got {value}"
        )


def validate_i2c_address(value: int) -> None:
    """Validate I2C device address.

    Args:
        value: I2C address to validate. Must be one of the valid
            addresses: 0x01, 0x02, 0x03.

    Raises:
        ValueError: If value is not in the set of valid I2C addresses.
    """
    if value not in VALID_I2C_ADDRESSES:
        raise ValueError(
            f"i2c_address must be one of {{{', '.join(hex(a) for a in VALID_I2C_ADDRESSES)}}}, "
            f"got {hex(value) if isinstance(value, int) else value!r}"
        )


def validate_lco_fdiv(value: int) -> None:
    """Validate LCO frequency division ratio.

    Args:
        value: LCO frequency division ratio to validate. Must be an
            integer in the range 0–3.

    Raises:
        ValueError: If value is not an integer or outside the range 0–3.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"lco_fdiv must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value < 0 or value > 3:
        raise ValueError(
            f"lco_fdiv must be in range 0–3, got {value}"
        )


def validate_min_strikes(value: int) -> None:
    """Validate minimum strikes value.

    Args:
        value: Minimum strikes value to validate. Must be one of
            the valid values: 1, 5, 9, 16.

    Raises:
        ValueError: If value is not an integer or not in the set of
            valid minimum strikes values.
    """
    if not isinstance(value, int):
        raise ValueError(
            f"min_strikes must be an integer, got {type(value).__name__}: {value!r}"
        )
    if value not in VALID_MIN_STRIKES:
        raise ValueError(
            f"min_strikes must be one of {{{', '.join(str(s) for s in VALID_MIN_STRIKES)}}}, "
            f"got {value!r}"
        )
