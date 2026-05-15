# DFRobot_AS3935

Modernized Python driver for the AS3935 Lightning Sensor on Raspberry Pi.

![Product Image](./resources/images/SEN0290.png)

## Summary

The AS3935 Lightning Sensor detects lightning and estimates the distance and intensity of strikes within 40 km, without interference from electric arcs or noise. This library provides a clean, type-safe Python interface for Raspberry Pi (tested on Pi Zero 2W with Raspberry Pi OS Bookworm).

- Lightning storm activity detection within a 40 km radius
- Distance estimation from overhead to 40 km in 15 steps
- Detects both cloud-to-ground and intra-cloud flashes
- Embedded man-made disturber rejection algorithm
- Programmable detection levels for optimal sensitivity control
- Three I2C addresses (0x01, 0x02, 0x03) via DIP switch

**SKU:** [SEN0290](https://www.dfrobot.com/product-1828.html)

## Requirements

- Python 3.11+
- Raspberry Pi OS Bookworm (or later)
- I2C enabled (`sudo raspi-config` → Interface Options → I2C)

## Installation

```bash
git clone https://github.com/DFRobot/DFRobot_AS3935.git
cd DFRobot_AS3935
pip install .
```

For development (with test dependencies):

```bash
pip install -e ".[test]"
```

## Quick Start

```python
from dfrobot_as3935 import DFRobot_AS3935, INT_LIGHTNING

with DFRobot_AS3935(address=0x03, bus=1, irq_pin=4) as sensor:
    sensor.set_indoors()
    sensor.set_noise_floor_level(2)

    def on_interrupt():
        source = sensor.get_interrupt_source()
        if source == INT_LIGHTNING:
            distance = sensor.get_lightning_distance_km()
            energy = sensor.get_strike_energy_normalized()
            print(f"Lightning! Distance: {distance} km, Energy: {energy:.4f}")

    sensor.register_interrupt_callback(on_interrupt)

    import signal
    signal.pause()  # Wait for events
```

## Wiring

| AS3935 Pin | Raspberry Pi Pin | Notes |
|-----------|-----------------|-------|
| VCC | 3.3V (pin 1) | |
| GND | GND (pin 6) | |
| SDA | BCM 2 (pin 3) | I2C1 data |
| SCL | BCM 3 (pin 5) | I2C1 clock |
| IRQ | BCM 4 (pin 7) | Interrupt output |

## API Reference

### Initialization

```python
DFRobot_AS3935(address=0x03, bus=1, irq_pin=4)
```

- `address`: I2C address — 0x01, 0x02, or 0x03 (set via DIP switch)
- `bus`: I2C bus number (default: 1)
- `irq_pin`: BCM GPIO pin for IRQ (default: 4)

Supports context manager (`with` statement) for automatic resource cleanup.

### Configuration Methods

| Method | Description |
|--------|-------------|
| `set_indoors()` | Set indoor AFE gain |
| `set_outdoors()` | Set outdoor AFE gain |
| `set_noise_floor_level(0–7)` | Set noise floor threshold |
| `get_noise_floor_level()` | Read current noise floor level |
| `set_watchdog_threshold(0–15)` | Set watchdog threshold |
| `get_watchdog_threshold()` | Read current watchdog threshold |
| `set_spike_rejection(0–15)` | Set spike rejection level |
| `get_spike_rejection()` | Read current spike rejection |
| `set_tuning_caps(0–120)` | Set antenna capacitance (multiple of 8) |
| `set_min_strikes(1/5/9/16)` | Set minimum strikes before interrupt |
| `set_lco_fdiv(0–3)` | Set LCO frequency division ratio |
| `set_irq_output_source(0–3)` | Set IRQ pin display source |
| `enable_disturber()` | Enable disturber detection |
| `disable_disturber()` | Disable disturber detection |
| `clear_statistics()` | Clear lightning statistics |
| `power_up()` | Power up the sensor |
| `power_down()` | Power down the sensor |
| `reset()` | Reset sensor to defaults |

### Data Reading Methods

| Method | Returns |
|--------|---------|
| `get_interrupt_source()` | Interrupt code: `INT_LIGHTNING` (0x08), `INT_DISTURBER` (0x04), `INT_NOISE` (0x01) |
| `get_lightning_distance_km()` | Estimated distance in km (0–63) |
| `get_strike_energy_raw()` | Raw 21-bit energy value (0–2,097,151) |
| `get_strike_energy_normalized()` | Normalized energy (0.0–1.0) |

### Interrupt Handling

```python
sensor.register_interrupt_callback(my_callback)  # Register
sensor.register_interrupt_callback(None)          # Clear
```

The callback is invoked in gpiozero's edge detection thread with the I2C lock held for thread safety.

### Resource Management

```python
# Context manager (recommended)
with DFRobot_AS3935(...) as sensor:
    ...

# Manual cleanup
sensor = DFRobot_AS3935(...)
try:
    ...
finally:
    sensor.close()
```

## Examples

- [`examples/lightning_detection.py`](examples/lightning_detection.py) — Interrupt-based lightning detection
- [`examples/sensor_configuration.py`](examples/sensor_configuration.py) — Sensor configuration demonstration

## Running Tests

```bash
pip install -e ".[test]"
python -m pytest tests/ -v
```

The test suite (295 tests) runs without hardware using mocked I2C and GPIO. Includes property-based tests via Hypothesis.

## Compatibility

| Board | Status |
|-------|--------|
| Raspberry Pi Zero 2W | ✓ Tested |
| Raspberry Pi 4 | ✓ Compatible |
| Raspberry Pi 3 | ✓ Compatible |
| Raspberry Pi 5 | ✓ Compatible (gpiozero) |

| Python | Status |
|--------|--------|
| 3.11+ | ✓ Required |

| OS | Status |
|----|--------|
| Raspberry Pi OS Bookworm | ✓ Tested |
| Raspberry Pi OS Bullseye | ✓ Compatible |

## Changes from v1.x (Legacy)

This is a complete rewrite of the original DFRobot library. Key changes:

- **Dependencies**: `smbus` → `smbus2`, `RPi.GPIO` → `gpiozero`
- **Package structure**: pip-installable via `pyproject.toml`
- **Thread safety**: All I2C access serialized with `threading.RLock`
- **Resource management**: Context manager support, deterministic cleanup
- **Input validation**: All parameters validated before hardware writes
- **Error handling**: Clear exceptions instead of silent failures or infinite loops
- **Bug fixes**: Corrected LCO bit (0x80), clear_statistics sequence, energy calculation
- **Type hints**: Full annotations for IDE support
- **Logging**: Structured logging via Python `logging` module (no print statements)
- **Testing**: 295 tests including property-based tests (Hypothesis)
- **Pin numbering**: BCM (gpiozero) instead of BOARD (RPi.GPIO)

The legacy code remains available in `python/raspberrypi/` for reference.

## License

MIT License — see [LICENSE](LICENSE)

## Credits

- Original library by TangJie (jie.Tang@dfrobot.com), DFRobot, 2019
- Modernization by Christian Kanzler, 2025
- [DFRobot Product Page](https://www.dfrobot.com/product-1828.html)
- [DFRobot Wiki](https://wiki.dfrobot.com/Gravity:%20Lightning%20Sensor%20SKU:%20sen0290)
