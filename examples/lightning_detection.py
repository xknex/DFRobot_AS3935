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


COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "info": "\033[36m",
    "lightning": "\033[32m",
    "disturber": "\033[33m",
    "noise": "\033[31m",
    "error": "\033[31m",
}


def log_event(level: str, message: str, *, color: str = "info") -> None:
    """Print a timestamped event line with ANSI color when supported."""
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if sys.stdout.isatty():
        print(
            f"{COLORS['dim']}{timestamp}{COLORS['reset']} "
            f"{COLORS[color]}{level:<9}{COLORS['reset']} {message}",
            flush=True,
        )
    else:
        print(f"{timestamp} {level:<9} {message}", flush=True)


def main() -> None:
    """Run lightning detection with interrupt-based callback."""
    # BCM pin 4 = physical pin 7 on the Raspberry Pi header
    IRQ_PIN = 4
    I2C_ADDRESS = 0x03
    I2C_BUS = 1
    NEAR_LIGHTNING_DISTANCE_KM = 5
    NEAR_LIGHTNING_MIN_ENERGY = 0.25

    try:
        with DFRobot_AS3935(address=I2C_ADDRESS, bus=I2C_BUS, irq_pin=IRQ_PIN) as sensor:
            # Configure sensor for outdoor use
            sensor.set_outdoors()
            sensor.set_tuning_caps(96)
            sensor.set_noise_floor_level(2)
            sensor.set_watchdog_threshold(2)
            sensor.set_spike_rejection(2)
            sensor.set_min_strikes(1)
            sensor.enable_disturber()
            sensor.set_irq_output_source(0)

            def interrupt_handler() -> None:
                """Handle interrupt events from the AS3935 sensor."""
                source = sensor.get_interrupt_source()

                if source == INT_LIGHTNING:
                    distance = sensor.get_lightning_distance_km()
                    energy = sensor.get_strike_energy_normalized()
                    if (
                        distance <= NEAR_LIGHTNING_DISTANCE_KM
                        and energy < NEAR_LIGHTNING_MIN_ENERGY
                    ):
                        log_event(
                            "SUSPECT",
                            f"Chip lightning: Distance: {distance} km, "
                            f"Energy: {energy:.4f} (near/weak signature)",
                            color="disturber",
                        )
                        return

                    log_event(
                        "LIGHTNING",
                        f"Distance: {distance} km, "
                        f"Energy: {energy:.4f}",
                        color="lightning",
                    )
                elif source == INT_DISTURBER:
                    log_event(
                        "DISTURBER",
                        "Disturber detected (not lightning)",
                        color="disturber",
                    )
                elif source == INT_NOISE:
                    log_event("NOISE", "Noise level too high", color="noise")

            sensor.register_interrupt_callback(interrupt_handler)

            log_event("INFO", "AS3935 Lightning Sensor ready.")
            log_event("INFO", f"I2C address: 0x{I2C_ADDRESS:02X}, bus: {I2C_BUS}")
            log_event("INFO", f"IRQ pin: BCM {IRQ_PIN} (physical pin 7)")
            log_event(
                "INFO",
                "Outdoor diagnostic profile: tuning=96pF, noise=2, watchdog=2, "
                "spike=2, min_strikes=1, disturber_irq=enabled, "
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


if __name__ == "__main__":
    main()
