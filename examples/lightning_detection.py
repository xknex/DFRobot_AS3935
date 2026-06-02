#!/usr/bin/env python3
"""Lightning detection example using interrupt-based callbacks.

Demonstrates the modernized DFRobot AS3935 library with:
- Context manager for automatic resource cleanup
- Interrupt callback for lightning event detection
- BCM pin numbering (gpiozero)
- Proper error handling for initialization failures

Hardware connections:
    AS3935 IRQ pin -> Raspberry Pi physical pin 7 (BCM GPIO 4)
    AS3935 SDA     -> Raspberry Pi physical pin 3 (BCM GPIO 2 / I2C1 SDA)
    AS3935 SCL     -> Raspberry Pi physical pin 5 (BCM GPIO 3 / I2C1 SCL)
    AS3935 VCC     -> 3.3V
    AS3935 GND     -> GND

Pin mapping reference:
    Physical pin 7 = BCM pin 4 (used for IRQ)
"""

import signal
import sys
from datetime import datetime

from dfrobot_as3935 import (
    DFRobot_AS3935,
    INT_DISTURBER,
    INT_LIGHTNING,
    INT_NOISE,
)


# ============================================================================
# Visual Constants
# ============================================================================

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "underline": "\033[4m",
    "info": "\033[36m",
    "lightning": "\033[38;5;226m",  # Bright yellow
    "lightning_glow": "\033[38;5;190m",  # Yellow with glow effect
    "disturber": "\033[38;5;208m",  # Orange
    "noise": "\033[38;5;196m",  # Red
    "error": "\033[38;5;196m",
    "status_bg": "\033[48;5;236m",  # Dark gray background
    "status_text": "\033[38;5;255m",  # White
}

# Unicode symbols
SYMBOLS = {
    "bolt": "\u26a1",
    "cloud": "\u2601",
    "cloud_lightning": "\u26c8",
    "warning": "\u26a0\ufe0f",
    "circle": "\u25cf",
    "circle_filled": "\u25a0",
    "bar_full": "\u2588",
    "bar_half": "\u2594",
    "arrow_right": "\u2192",
    "dash": "\u2014",
}

# ============================================================================
# Visual Helpers
# ============================================================================


def _color(code: str) -> str:
    """Get ANSI color code."""
    return COLORS.get(code, "")


def _symbol(name: str) -> str:
    """Get Unicode symbol."""
    return SYMBOLS.get(name, "?")


def log_event(level: str, message: str, *, color: str = "info") -> None:
    """Print a timestamped event line with ANSI color when supported."""
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if sys.stdout.isatty():
        print(
            f"{_color('dim')}{timestamp}{_color('reset')} "
            f"{_color(color)}{level:<9}{_color('reset')} {message}",
            flush=True,
        )
    else:
        print(f"{timestamp} {level:<9} {message}", flush=True)


def print_lightning_event(
    *,
    distance: int,
    energy: float,
    distance_is_unconverged: bool,
    events_since_last: int,
    disturber_count: int,
    noise_count: int,
) -> None:
    """Print a beautiful lightning event with counts of events in between."""
    if not sys.stdout.isatty():
        # Plain text output for non-TTY environments
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{timestamp} LIGHTNING | Distance: {distance} km "
            f"{'(unconverged)' if distance_is_unconverged else ''}, "
            f"Energy: {energy:.4f} | "
            f"Events since last: {events_since_last} "
            f"(Disturb: {disturber_count}, Noise: {noise_count})"
        )
        return

    # Colorful output for TTY
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    event_type = "(unconverged)" if distance_is_unconverged else ""

    print()
    print(f"  {_color('lightning_glow')}{_symbol('bolt')}{_color('reset')}" * 20)
    print(f"{_color('lightning_glow')}  {_symbol('cloud_lightning')}  LIGHTNING STRIKE DETECTED!  {_symbol('cloud_lightning')}{_color('reset')}")
    print(f"  {_color('lightning_glow')}{_symbol('bolt')}{_color('reset')}" * 20)
    print(f"{_color('dim')}{timestamp}{_color('reset')}")
    print(f"  Distance: {distance} km {event_type}")
    print(f"  Energy:   {energy:.4f}")
    print(f"  Events since last: {events_since_last}")
    print(f"    {_color('disturber')}{_symbol('warning')} Disturb: {disturber_count}{_color('reset')}")
    print(f"    {_color('noise')}{_symbol('circle_filled')} Noise: {noise_count}{_color('reset')}")
    print(f"  {_color('lightning_glow')}{_symbol('bolt')}{_color('reset')}" * 20)


def main() -> None:
    """Run lightning detection with interrupt-based callback."""
    # BCM pin 4 = physical pin 7 on the Raspberry Pi header
    IRQ_PIN = 4
    I2C_ADDRESS = 0x03
    I2C_BUS = 1
    NEAR_LIGHTNING_DISTANCE_KM = 5
    NEAR_LIGHTNING_MIN_ENERGY = 0.25
    UNCONVERGED_MIN_ENERGY = 0.30

    # Counters for storm statistics
    lightning_count = 0
    disturber_count = 0
    noise_count = 0
    events_since_last_lightning = 0
    total_disturbers_since_last = 0
    total_noise_since_last = 0

    try:
        with DFRobot_AS3935(address=I2C_ADDRESS, bus=I2C_BUS, irq_pin=IRQ_PIN) as sensor:
            # Configure sensor for outdoor use with sensitive settings
            sensor.set_outdoors()
            sensor.set_tuning_caps(96)
            sensor.set_noise_floor_level(1)  # Lower = more sensitive to weak signals
            sensor.set_watchdog_threshold(1)  # Lower = less strict disturber filtering
            sensor.set_spike_rejection(2)
            sensor.set_min_strikes(5)
            sensor.enable_disturber()
            sensor.set_irq_output_source(0)

            def interrupt_handler() -> None:
                """Handle interrupt events from the AS3935 sensor."""
                nonlocal lightning_count, disturber_count, noise_count
                nonlocal events_since_last_lightning
                nonlocal total_disturbers_since_last, total_noise_since_last

                source = sensor.get_interrupt_source()

                if source == INT_LIGHTNING:
                    distance = sensor.get_lightning_distance_km()
                    energy = sensor.get_strike_energy_normalized()

                    # Unconverged distance bypass: distance == 1 is the AS3935's
                    # default when the algorithm hasn't converged. Skip filter
                    # only if energy is high enough to likely be real lightning.
                    if distance == 1 and energy < UNCONVERGED_MIN_ENERGY:
                        # Bypass filter - this is likely noise, not real lightning
                        events_since_last_lightning += 1
                        return

                    # Print the lightning event with counts of events since last
                    distance_is_unconverged = distance == 1
                    print_lightning_event(
                        distance=distance,
                        energy=energy,
                        distance_is_unconverged=distance_is_unconverged,
                        events_since_last=events_since_last_lightning,
                        disturber_count=total_disturbers_since_last,
                        noise_count=total_noise_since_last,
                    )

                    # Reset counters
                    events_since_last_lightning = 0
                    total_disturbers_since_last = 0
                    total_noise_since_last = 0
                    lightning_count += 1

                elif source == INT_DISTURBER:
                    events_since_last_lightning += 1
                    total_disturbers_since_last += 1
                    disturber_count += 1

                elif source == INT_NOISE:
                    events_since_last_lightning += 1
                    total_noise_since_last += 1
                    noise_count += 1

            sensor.register_interrupt_callback(interrupt_handler)

            # Print startup info
            log_event("INFO", "AS3935 Lightning Sensor ready.")
            log_event("INFO", f"I2C address: 0x{I2C_ADDRESS:02X}, bus: {I2C_BUS}")
            log_event("INFO", f"IRQ pin: BCM {IRQ_PIN} (physical pin 7)")
            log_event(
                "INFO",
                "Outdoor diagnostic profile: tuning=96pF, noise=1, watchdog=1, "
                "spike=2, min_strikes=5, disturber_irq=enabled, "
                "irq_output=events, "
                f"suspect<= {NEAR_LIGHTNING_DISTANCE_KM}km "
                f"when energy<{NEAR_LIGHTNING_MIN_ENERGY:.2f}",
            )
            log_event("INFO", "Waiting for lightning events... (Ctrl+C to exit)")

            # Keep the script running until interrupted
            signal.pause()

    except ConnectionError as e:
        log_event("ERROR", f"Sensor connection failed: {e}", color="error")
        sys.exit(1)
    except OSError as e:
        log_event("ERROR", f"I2C communication error: {e}", color="error")
        sys.exit(1)
    except KeyboardInterrupt:
        log_event("INFO", "Shutting down.")
