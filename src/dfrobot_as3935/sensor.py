"""AS3935 Lightning Sensor driver — main sensor class.

Provides the :class:`DFRobot_AS3935` class which communicates with the AS3935
lightning sensor IC over I2C using ``smbus2`` and detects interrupt events via
``gpiozero``.

All I2C access is serialized with a :class:`threading.RLock` to prevent
corruption when interrupt callbacks fire concurrently with main-thread
operations.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import smbus2
from gpiozero import DigitalInputDevice

from dfrobot_as3935.constants import (
    AFE_GAIN_INDOOR,
    AFE_GAIN_OUTDOOR,
    CMD_CALIB_RCO,
    CMD_PRESET_DEFAULT,
    MASK_AFE_GAIN,
    MASK_CL_STAT,
    MASK_DISP_FLAGS,
    MASK_DISP_LCO,
    MASK_DISP_SRCO,
    MASK_DISP_TRCO,
    MASK_DISTANCE,
    MASK_ENERGY_MMSB,
    MASK_INT,
    MASK_LCO_FDIV,
    MASK_MASK_DIST,
    MASK_MIN_NUM_LIGH,
    MASK_NF_LEV,
    MASK_SREJ,
    MASK_TUN_CAP,
    MASK_WDTH,
    REG_AFE_GAIN,
    REG_CALIB_RCO,
    REG_DISP_TUNE,
    REG_DISTANCE,
    REG_ENERGY_LSB,
    REG_ENERGY_MSB,
    REG_ENERGY_MMSB,
    REG_INT_MASK_ANT,
    REG_LIGHTNING,
    REG_PRESET_DEFAULT,
    REG_THRESHOLD,
)
from dfrobot_as3935.validators import (
    validate_capacitance,
    validate_i2c_address,
    validate_lco_fdiv,
    validate_min_strikes,
    validate_noise_floor_level,
    validate_spike_rejection,
    validate_watchdog_threshold,
)

logger = logging.getLogger("dfrobot_as3935")
logger.addHandler(logging.NullHandler())


class DFRobot_AS3935:
    """AS3935 Lightning Sensor driver for Raspberry Pi.

    Communicates with the AS3935 IC over I2C and detects lightning
    events via GPIO interrupt on the IRQ pin.

    Usage::

        with DFRobot_AS3935(address=0x03, bus=1, irq_pin=4) as sensor:
            sensor.set_indoors()
            sensor.register_interrupt_callback(my_handler)

    Args:
        address: I2C device address. Must be one of 0x01, 0x02, 0x03.
        bus: I2C bus number. Defaults to 1.
        irq_pin: BCM GPIO pin number for the IRQ line. Defaults to 4.
    """

    def __init__(self, address: int, bus: int = 1, irq_pin: int = 4) -> None:
        """Initialize the AS3935 sensor driver.

        Validates parameters, opens the I2C bus, configures the GPIO IRQ pin,
        and resets the sensor with retry logic. Uses phased error recovery to
        clean up partially acquired resources on failure.

        Args:
            address: I2C device address. Must be one of 0x01, 0x02, 0x03.
            bus: I2C bus number. Defaults to 1.
            irq_pin: BCM GPIO pin number for the IRQ line. Defaults to 4.

        Raises:
            ValueError: If the I2C address is not valid.
            OSError: If the I2C bus cannot be opened.
            ConnectionError: If the sensor does not respond after retries.
        """
        self._lock: threading.RLock = threading.RLock()
        self._closed: bool = False
        self._callback = None

        # Phase 1: Validate parameters (no resources acquired)
        validate_i2c_address(address)
        self._address: int = address
        self._bus_number: int = bus
        self._irq_pin: int = irq_pin

        # Phase 2: Acquire I2C bus
        try:
            self._bus: smbus2.SMBus = smbus2.SMBus(bus)
        except OSError as e:
            logger.warning("Failed to open I2C bus %d: %s", bus, e)
            raise OSError(f"Failed to open I2C bus {bus}: {e}") from e

        # Phase 3: Acquire GPIO (cleanup bus on failure)
        try:
            self._irq_device: DigitalInputDevice = DigitalInputDevice(
                irq_pin, pull_up=None
            )
        except Exception:
            self._bus.close()
            raise

        # Phase 4: Reset sensor (cleanup both on failure)
        try:
            self._reset_with_retry()
        except Exception:
            self._irq_device.close()
            self._bus.close()
            raise

    def __enter__(self) -> "DFRobot_AS3935":
        """Enter the context manager.

        Returns:
            The sensor instance.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit the context manager, releasing all resources.

        Does not suppress exceptions.

        Returns:
            False (never suppresses exceptions).
        """
        self.close()
        return False

    def close(self) -> None:
        """Release GPIO and I2C resources.

        Safe to call multiple times without raising an exception.
        Attempts to close both resources even if one fails.

        Raises:
            Exception: If resource cleanup fails (first error is raised).
        """
        if self._closed:
            return
        self._closed = True
        errors: list[Exception] = []
        try:
            self._irq_device.close()
        except Exception as e:
            errors.append(e)
        try:
            self._bus.close()
        except Exception as e:
            errors.append(e)
        if errors:
            raise errors[0]

    def _ensure_open(self) -> None:
        """Check that the sensor has not been closed.

        Raises:
            RuntimeError: If close() has been called.
        """
        if self._closed:
            raise RuntimeError("Sensor resource has been closed")

    def _read_register(self, register: int) -> int:
        """Read a single byte from an I2C register.

        Acquires the RLock before performing the I2C read and releases it
        afterwards. Wraps any I2C errors in an OSError with diagnostic context.

        Args:
            register: Register address to read from (0x00–0x3D).

        Returns:
            The byte value read from the register (0–255).

        Raises:
            OSError: If the I2C read operation fails. The message includes
                the register address, device address, and underlying cause.
        """
        with self._lock:
            try:
                value = self._bus.read_byte_data(self._address, register)
                logger.debug(
                    "I2C read: register=0x%02X, value=0x%02X, device=0x%02X",
                    register,
                    value,
                    self._address,
                )
                return value
            except OSError as e:
                raise OSError(
                    f"I2C read failed: register=0x{register:02X}, "
                    f"device=0x{self._address:02X}, cause: {e}"
                ) from e

    def _write_register(self, register: int, value: int) -> None:
        """Write a single byte to an I2C register.

        Acquires the RLock before performing the I2C write and releases it
        afterwards. Wraps any I2C errors in an OSError with diagnostic context.

        Args:
            register: Register address to write to (0x00–0x3D).
            value: Byte value to write (0–255).

        Raises:
            OSError: If the I2C write operation fails. The message includes
                the register address, device address, and underlying cause.
        """
        with self._lock:
            try:
                self._bus.write_byte_data(self._address, register, value)
                logger.debug(
                    "I2C write: register=0x%02X, value=0x%02X, device=0x%02X",
                    register,
                    value,
                    self._address,
                )
            except OSError as e:
                raise OSError(
                    f"I2C write failed: register=0x{register:02X}, "
                    f"device=0x{self._address:02X}, cause: {e}"
                ) from e

    def _read_modify_write(self, register: int, mask: int, value: int) -> None:
        """Read a register, modify specific bits, and write back.

        Performs an atomic read-modify-write operation under the RLock.
        The mask indicates which bits to modify. The value should be
        pre-shifted to the correct bit position.

        Operation:
            1. Read current register value
            2. Clear the bits indicated by mask: ``current & ~mask``
            3. Set new bits: ``cleared | (value & mask)``
            4. Write the result back to the register

        Args:
            register: Register address to modify (0x00–0x3D).
            mask: Bitmask indicating which bits to modify.
            value: New value for the masked bits, pre-shifted to the
                correct position.

        Raises:
            OSError: If any I2C operation fails. The message includes
                the register address, device address, and underlying cause.
        """
        with self._lock:
            try:
                current = self._bus.read_byte_data(self._address, register)
                logger.debug(
                    "I2C read: register=0x%02X, value=0x%02X, device=0x%02X",
                    register,
                    current,
                    self._address,
                )
                new_value = (current & ~mask) | (value & mask)
                self._bus.write_byte_data(self._address, register, new_value)
                logger.debug(
                    "I2C write: register=0x%02X, value=0x%02X, device=0x%02X",
                    register,
                    new_value,
                    self._address,
                )
            except OSError as e:
                raise OSError(
                    f"I2C read-modify-write failed: register=0x{register:02X}, "
                    f"device=0x{self._address:02X}, cause: {e}"
                ) from e

    def _reset_with_retry(self) -> None:
        """Reset the sensor with retry logic.

        Sends the PRESET_DEFAULT command and verifies the sensor responds.
        Retries up to 3 times with ~333ms between attempts (total ~1000ms).
        After a successful reset, calibrates the internal RC oscillators.

        Raises:
            ConnectionError: If the sensor does not respond after 3 attempts.
        """
        max_attempts = 3
        delay_between_attempts = 0.333  # ~333ms between attempts

        for attempt in range(max_attempts):
            try:
                # Send reset command
                self._write_register(REG_PRESET_DEFAULT, CMD_PRESET_DEFAULT)
                # Wait 2ms for reset to complete per datasheet
                time.sleep(0.002)
                # Try to read a register to verify sensor is responsive
                self._read_register(0x00)
                # Sensor responded — calibrate RCO and return
                self._write_register(REG_CALIB_RCO, CMD_CALIB_RCO)
                return
            except OSError:
                if attempt < max_attempts - 1:
                    time.sleep(delay_between_attempts)

        # All attempts failed
        logger.warning(
            "Sensor at address 0x%02X on bus %d did not respond after %d attempts",
            self._address,
            self._bus_number,
            max_attempts,
        )
        raise ConnectionError(
            f"Sensor at address 0x{self._address:02X} on bus {self._bus_number} "
            f"did not respond after {max_attempts} attempts"
        )

    # ------------------------------------------------------------------
    # Configuration Methods
    # ------------------------------------------------------------------

    def set_indoors(self) -> None:
        """Set the analog front-end gain for indoor operation.

        Writes the indoor AFE gain value (0x24) to the AFE_GAIN register
        bits using a read-modify-write operation.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        self._read_modify_write(REG_AFE_GAIN, MASK_AFE_GAIN, AFE_GAIN_INDOOR)
        logger.info("Configuration changed: mode=indoor (AFE gain=0x%02X)", AFE_GAIN_INDOOR)

    def set_outdoors(self) -> None:
        """Set the analog front-end gain for outdoor operation.

        Writes the outdoor AFE gain value (0x1C) to the AFE_GAIN register
        bits using a read-modify-write operation.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        self._read_modify_write(REG_AFE_GAIN, MASK_AFE_GAIN, AFE_GAIN_OUTDOOR)
        logger.info("Configuration changed: mode=outdoor (AFE gain=0x%02X)", AFE_GAIN_OUTDOOR)

    def set_noise_floor_level(self, level: int) -> None:
        """Set the noise floor level threshold.

        Args:
            level: Noise floor level in the range 0–7. Higher values
                make the sensor less sensitive to noise.

        Raises:
            ValueError: If level is not an integer or outside 0–7.
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_noise_floor_level(level)
        shifted_value = (level << 4) & MASK_NF_LEV
        self._read_modify_write(REG_THRESHOLD, MASK_NF_LEV, shifted_value)
        logger.info("Configuration changed: noise_floor_level=%d", level)

    def get_noise_floor_level(self) -> int:
        """Get the current noise floor level threshold.

        Returns:
            The noise floor level in the range 0–7.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        reg_value = self._read_register(REG_THRESHOLD)
        return (reg_value & MASK_NF_LEV) >> 4

    def set_watchdog_threshold(self, threshold: int) -> None:
        """Set the watchdog threshold.

        Args:
            threshold: Watchdog threshold in the range 0–15. Higher values
                reduce false triggers but may miss weaker signals.

        Raises:
            ValueError: If threshold is not an integer or outside 0–15.
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_watchdog_threshold(threshold)
        self._read_modify_write(REG_THRESHOLD, MASK_WDTH, threshold & MASK_WDTH)
        logger.info("Configuration changed: watchdog_threshold=%d", threshold)

    def get_watchdog_threshold(self) -> int:
        """Get the current watchdog threshold.

        Returns:
            The watchdog threshold in the range 0–15.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        reg_value = self._read_register(REG_THRESHOLD)
        return reg_value & MASK_WDTH

    def set_spike_rejection(self, rejection: int) -> None:
        """Set the spike rejection level.

        Args:
            rejection: Spike rejection value in the range 0–15. Higher
                values provide more robust spike rejection.

        Raises:
            ValueError: If rejection is not an integer or outside 0–15.
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_spike_rejection(rejection)
        self._read_modify_write(REG_LIGHTNING, MASK_SREJ, rejection & MASK_SREJ)
        logger.info("Configuration changed: spike_rejection=%d", rejection)

    def get_spike_rejection(self) -> int:
        """Get the current spike rejection level.

        Returns:
            The spike rejection value in the range 0–15.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        reg_value = self._read_register(REG_LIGHTNING)
        return reg_value & MASK_SREJ

    def set_tuning_caps(self, capacitance: int) -> None:
        """Set the antenna tuning capacitance.

        The capacitance value is divided by 8 (shifted right by 3) before
        being written to the TUN_CAP register bits.

        Args:
            capacitance: Capacitance value. Must be a multiple of 8 in
                the range 0–120 (pF).

        Raises:
            ValueError: If capacitance is not valid (not int, not multiple
                of 8, or outside 0–120).
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_capacitance(capacitance)
        register_value = (capacitance >> 3) & MASK_TUN_CAP
        self._read_modify_write(REG_DISP_TUNE, MASK_TUN_CAP, register_value)
        logger.info("Configuration changed: tuning_caps=%d pF", capacitance)

    def set_min_strikes(self, strikes: int) -> None:
        """Set the minimum number of lightning strikes for interrupt.

        Maps the strikes value to the register encoding:
        - 1 → 0x00
        - 5 → 0x10
        - 9 → 0x20
        - 16 → 0x30

        Args:
            strikes: Minimum number of strikes. Must be one of 1, 5, 9, 16.

        Raises:
            ValueError: If strikes is not one of the valid values.
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_min_strikes(strikes)
        strikes_encoding = {1: 0x00, 5: 0x10, 9: 0x20, 16: 0x30}
        register_value = strikes_encoding[strikes]
        self._read_modify_write(REG_LIGHTNING, MASK_MIN_NUM_LIGH, register_value)
        logger.info("Configuration changed: min_strikes=%d", strikes)

    def set_lco_fdiv(self, division: int) -> None:
        """Set the LCO frequency division ratio.

        The division value is shifted left by 6 before being written to
        the LCO_FDIV register bits.

        Args:
            division: Frequency division ratio in the range 0–3.
                - 0: divide by 16
                - 1: divide by 32
                - 2: divide by 64
                - 3: divide by 128

        Raises:
            ValueError: If division is not an integer or outside 0–3.
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_lco_fdiv(division)
        register_value = (division << 6) & MASK_LCO_FDIV
        self._read_modify_write(REG_INT_MASK_ANT, MASK_LCO_FDIV, register_value)
        logger.info("Configuration changed: lco_fdiv=%d", division)

    def set_irq_output_source(self, source: int) -> None:
        """Set the IRQ output source for display on the IRQ pin.

        Clears all display flags first, then sets the appropriate bit:
        - 0: No display (all clear)
        - 1: TRCO (0x20)
        - 2: SRCO (0x40)
        - 3: LCO (0x80) — Note: this is the corrected value per datasheet

        Args:
            source: Display source selection (0–3).

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        # Clear all display flags first
        self._read_modify_write(REG_DISP_TUNE, MASK_DISP_FLAGS, 0x00)
        # Set the appropriate display bit
        if source == 1:
            self._read_modify_write(REG_DISP_TUNE, MASK_DISP_FLAGS, MASK_DISP_TRCO)
        elif source == 2:
            self._read_modify_write(REG_DISP_TUNE, MASK_DISP_FLAGS, MASK_DISP_SRCO)
        elif source == 3:
            self._read_modify_write(REG_DISP_TUNE, MASK_DISP_FLAGS, MASK_DISP_LCO)
        logger.info("Configuration changed: irq_output_source=%d", source)

    def enable_disturber(self) -> None:
        """Enable disturber detection.

        Clears the MASK_DIST bit in the INT_MASK_ANT register.
        When the bit is 0, disturber events generate interrupts.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        self._read_modify_write(REG_INT_MASK_ANT, MASK_MASK_DIST, 0x00)
        logger.info("Configuration changed: disturber=enabled")

    def disable_disturber(self) -> None:
        """Disable disturber detection.

        Sets the MASK_DIST bit in the INT_MASK_ANT register.
        When the bit is 1, disturber events are masked (no interrupt).

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        self._read_modify_write(REG_INT_MASK_ANT, MASK_MASK_DIST, MASK_MASK_DIST)
        logger.info("Configuration changed: disturber=disabled")

    def clear_statistics(self) -> None:
        """Clear the lightning statistics.

        Toggles the CL_STAT bit (register 0x02, bit 6) using exactly 4 writes
        in the sequence: set low, set high, set low, set high, per the AS3935
        datasheet.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        self._read_modify_write(REG_LIGHTNING, MASK_CL_STAT, 0x00)
        self._read_modify_write(REG_LIGHTNING, MASK_CL_STAT, MASK_CL_STAT)
        self._read_modify_write(REG_LIGHTNING, MASK_CL_STAT, 0x00)
        self._read_modify_write(REG_LIGHTNING, MASK_CL_STAT, MASK_CL_STAT)
        logger.info("Statistics cleared")

    def configure(
        self,
        *,
        capacitance: int = 96,
        indoor: bool = True,
        disturber: bool = True,
    ) -> None:
        """Configure the sensor in a single convenience call.

        This is a higher-level method that sets the AFE gain mode, disturber
        detection, and antenna tuning capacitance in one call. Equivalent to
        the legacy ``manual_cal()`` method from the original library.

        Args:
            capacitance: Antenna tuning capacitance in pF. Must be a multiple
                of 8 in the range 0–120. Defaults to 96.
            indoor: If True, set indoor AFE gain; if False, set outdoor.
                Defaults to True.
            disturber: If True, enable disturber detection; if False, disable
                it. Defaults to True.

        Raises:
            ValueError: If capacitance is not valid (not int, not multiple
                of 8, or outside 0–120).
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        validate_capacitance(capacitance)

        if indoor:
            self.set_indoors()
        else:
            self.set_outdoors()

        if disturber:
            self.enable_disturber()
        else:
            self.disable_disturber()

        self.set_tuning_caps(capacitance)
        logger.info(
            "Sensor configured: indoor=%s, disturber=%s, capacitance=%d pF",
            indoor,
            disturber,
            capacitance,
        )

    # ------------------------------------------------------------------
    # Interrupt Handling
    # ------------------------------------------------------------------

    def register_interrupt_callback(
        self, callback: Callable[[], None] | None
    ) -> None:
        """Register or clear the interrupt callback for rising-edge events.

        Sets the ``when_activated`` handler on the gpiozero
        :class:`DigitalInputDevice` for the IRQ pin. The user-provided
        callback is wrapped so that the internal :class:`threading.RLock` is
        acquired before the callback executes, ensuring thread-safe access
        to I2C operations within the callback context.

        Replacing a callback simply overwrites the previous one. If
        ``callback`` is ``None``, the interrupt is silently ignored (no
        handler is invoked on rising edge).

        The callback is invoked within gpiozero's edge detection thread.

        Args:
            callback: A callable with no arguments to invoke on interrupt,
                or ``None`` to clear the current callback and ignore
                subsequent interrupts.

        Raises:
            RuntimeError: If the sensor has been closed.
        """
        self._ensure_open()

        if callback is None:
            self._callback = None
            self._irq_device.when_activated = None
            logger.info("Interrupt callback cleared")
            return

        self._callback = callback

        def _wrapped_callback(device: object) -> None:
            """Wrapper that acquires the RLock before invoking user callback."""
            with self._lock:
                self._callback()  # type: ignore[misc]

        self._irq_device.when_activated = _wrapped_callback
        logger.info("Interrupt callback registered")

    # ------------------------------------------------------------------
    # Data Reading Methods
    # ------------------------------------------------------------------

    def get_interrupt_source(self) -> int:
        """Read the interrupt source register.

        Waits 3ms per the AS3935 datasheet before reading the interrupt
        register to allow the IC to settle.

        Returns:
            The interrupt source code:
            - 0x08: Lightning detected
            - 0x04: Disturber detected
            - 0x01: Noise level too high

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        time.sleep(0.003)
        reg_value = self._read_register(REG_INT_MASK_ANT)
        return reg_value & MASK_INT

    def get_lightning_distance_km(self) -> int:
        """Read the estimated lightning distance in kilometers.

        Returns:
            The estimated distance in km (0–63). A value of 63 means
            "out of range".

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        reg_value = self._read_register(REG_DISTANCE)
        return reg_value & MASK_DISTANCE

    def get_strike_energy_raw(self) -> int:
        """Read the raw 21-bit strike energy value.

        Combines registers 0x04 (LSB), 0x05 (MSB), and 0x06 (MMSB, bits 4:0)
        into a 21-bit unsigned integer without any division or scaling.

        Returns:
            The raw energy value in the range 0 to 2,097,151.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        lsb = self._read_register(REG_ENERGY_LSB)
        msb = self._read_register(REG_ENERGY_MSB)
        mmsb = self._read_register(REG_ENERGY_MMSB) & MASK_ENERGY_MMSB
        return (mmsb << 16) | (msb << 8) | lsb

    def get_strike_energy_normalized(self) -> float:
        """Read the strike energy as a normalized float.

        Divides the raw 21-bit energy value by 2,097,151 (2^21 - 1) to
        produce a value in the range [0.0, 1.0].

        Returns:
            The normalized energy value in the range 0.0 to 1.0.

        Raises:
            RuntimeError: If the sensor has been closed.
            OSError: If the I2C operation fails.
        """
        self._ensure_open()
        raw = self.get_strike_energy_raw()
        return raw / 2_097_151


