#!/usr/bin/env python3
"""AS3935 Lightning Sensor — Configuration Example.

Demonstrates how to configure the AS3935 lightning sensor using the
modernized dfrobot_as3935 package. Shows indoor/outdoor mode selection,
noise floor level, watchdog threshold, spike rejection, antenna tuning
capacitance, minimum strikes, and LCO frequency division ratio.

Hardware setup:
    - AS3935 connected via I2C (bus 1, address 0x03)
    - IRQ pin connected to Raspberry Pi physical pin 7 (BCM pin 4)

Requirements:
    - Python 3.11+
    - dfrobot_as3935 package installed (pip install .)
"""

from dfrobot_as3935 import DFRobot_AS3935


def main() -> None:
    """Configure the AS3935 sensor and read back current settings."""
    # BCM pin 4 = physical pin 7 on the Raspberry Pi GPIO header
    IRQ_PIN = 4
    I2C_ADDRESS = 0x03
    I2C_BUS = 1

    try:
        with DFRobot_AS3935(address=I2C_ADDRESS, bus=I2C_BUS, irq_pin=IRQ_PIN) as sensor:
            print("AS3935 sensor initialized successfully.")
            print()

            # --- Indoor/Outdoor Mode ---
            # Indoor mode uses higher AFE gain for better sensitivity indoors
            print("Setting indoor mode...")
            sensor.set_indoors()
            print("  Mode: Indoor")

            # To switch to outdoor mode (lower gain to avoid saturation):
            # sensor.set_outdoors()
            print()

            # --- Noise Floor Level ---
            # Range: 0–7. Higher values reduce noise sensitivity.
            print("Setting noise floor level to 2...")
            sensor.set_noise_floor_level(2)
            current_nf = sensor.get_noise_floor_level()
            print(f"  Noise floor level: {current_nf}")
            print()

            # --- Watchdog Threshold ---
            # Range: 0–15. Higher values reduce false triggers.
            print("Setting watchdog threshold to 2...")
            sensor.set_watchdog_threshold(2)
            current_wdth = sensor.get_watchdog_threshold()
            print(f"  Watchdog threshold: {current_wdth}")
            print()

            # --- Spike Rejection ---
            # Range: 0–15. Higher values provide more robust spike rejection.
            print("Setting spike rejection to 2...")
            sensor.set_spike_rejection(2)
            current_srej = sensor.get_spike_rejection()
            print(f"  Spike rejection: {current_srej}")
            print()

            # --- Antenna Tuning Capacitance ---
            # Must be a multiple of 8 in range 0–120 (pF).
            # Adjust to match your antenna's resonant frequency to 500 kHz.
            print("Setting tuning capacitance to 96 pF...")
            sensor.set_tuning_caps(96)
            print("  Tuning capacitance: 96 pF")
            print()

            # --- Minimum Strikes ---
            # Valid values: 1, 5, 9, 16
            # Number of lightning events in 15 minutes before interrupt.
            print("Setting minimum strikes to 1...")
            sensor.set_min_strikes(1)
            print("  Minimum strikes: 1")
            print()

            # --- LCO Frequency Division Ratio ---
            # Range: 0–3 (divides by 16, 32, 64, 128 respectively)
            # Used when outputting the LCO signal on the IRQ pin for tuning.
            print("Setting LCO frequency division ratio to 0 (divide by 16)...")
            sensor.set_lco_fdiv(0)
            print("  LCO frequency division: 0 (divide by 16)")
            print()

            print("Configuration complete.")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except ConnectionError as e:
        print(f"Sensor connection failed: {e}")
    except OSError as e:
        print(f"I2C communication error: {e}")


if __name__ == "__main__":
    main()
