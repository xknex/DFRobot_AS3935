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

from dfrobot_as3935 import (
    DFRobot_AS3935,
    INT_DISTURBER,
    INT_LIGHTNING,
    INT_NOISE,
)


def main() -> None:
    """Run lightning detection with interrupt-based callback."""
    # BCM pin 4 = physical pin 7 on the Raspberry Pi header
    IRQ_PIN = 4
    I2C_ADDRESS = 0x03
    I2C_BUS = 1

    try:
        with DFRobot_AS3935(address=I2C_ADDRESS, bus=I2C_BUS, irq_pin=IRQ_PIN) as sensor:
            # Configure sensor for indoor use
            sensor.set_indoors()
            sensor.set_noise_floor_level(2)
            sensor.set_watchdog_threshold(2)
            sensor.set_spike_rejection(2)
            sensor.set_min_strikes(1)

            def interrupt_handler() -> None:
                """Handle interrupt events from the AS3935 sensor."""
                source = sensor.get_interrupt_source()

                if source == INT_LIGHTNING:
                    distance = sensor.get_lightning_distance_km()
                    energy = sensor.get_strike_energy_normalized()
                    print(
                        f"Lightning detected! "
                        f"Distance: {distance} km, "
                        f"Energy: {energy:.4f}"
                    )
                elif source == INT_DISTURBER:
                    print("Disturber detected (not lightning)")
                elif source == INT_NOISE:
                    print("Noise level too high")

            sensor.register_interrupt_callback(interrupt_handler)

            print("AS3935 Lightning Sensor ready.")
            print(f"  I2C address: 0x{I2C_ADDRESS:02X}, bus: {I2C_BUS}")
            print(f"  IRQ pin: BCM {IRQ_PIN} (physical pin 7)")
            print("Waiting for lightning events... (Ctrl+C to exit)")

            # Keep the script running until interrupted
            signal.pause()

    except ConnectionError as e:
        print(f"Sensor connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"I2C communication error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down.")


if __name__ == "__main__":
    main()
