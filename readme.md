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
- For the Lightning Data Pipeline: `libmariadb-dev` and `python3-dev` (`sudo apt install libmariadb-dev python3-dev`)

## Installation

Raspberry Pi OS Bookworm uses an externally-managed Python environment (PEP 668), so you need a virtual environment:

```bash
git clone https://github.com/DFRobot/DFRobot_AS3935.git
cd DFRobot_AS3935
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

For development (with test dependencies):

```bash
source .venv/bin/activate
pip install -e ".[test]"
```

Activate the venv before running scripts:

```bash
source ~/DFRobot_AS3935/.venv/bin/activate
python examples/lightning_detection.py
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

The test suite (364 tests) runs without hardware using mocked I2C and GPIO. Includes property-based tests via Hypothesis covering the sensor driver, collector components, configuration, and REST API.

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
- **Testing**: 364 tests including property-based tests (Hypothesis)
- **Pin numbering**: BCM (gpiozero) instead of BOARD (RPi.GPIO)

The legacy code remains available in `python/raspberrypi/` for reference.

## Lightning Data Pipeline

The Lightning Data Pipeline extends this sensor driver with two independent services for continuous event collection and data access, designed for Raspberry Pi Zero 2W.

### Services

| Service | Description | Entry Point |
|---------|-------------|-------------|
| **Collector** | Long-running daemon that detects AS3935 interrupt events, writes each event to a local CSV file and a remote MariaDB database | `python -m lightning_collector` |
| **REST API** | FastAPI application serving lightning event data from MariaDB over HTTP for browser-based dashboards | `python -m lightning_api` |

Both services are managed by systemd with automatic restart on failure.

### Configuration

Configuration is loaded from environment variables (prefix `LIGHTNING_`) with an optional fallback to a TOML file (`lightning.toml`). Environment variables always take priority over TOML values.

#### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LIGHTNING_DB_HOST` | MariaDB host address | — | Yes |
| `LIGHTNING_DB_PORT` | MariaDB port (1–65535) | — | Yes |
| `LIGHTNING_DB_USER` | MariaDB username | — | Yes |
| `LIGHTNING_DB_PASSWORD` | MariaDB password | — | Yes |
| `LIGHTNING_DB_NAME` | MariaDB database name | — | Yes |
| `LIGHTNING_CSV_FILE_PATH` | Path to local CSV file | `/var/lib/lightning/events.csv` | No |
| `LIGHTNING_SENSOR_I2C_ADDRESS` | I2C address (0x01, 0x02, 0x03) | `0x03` | No |
| `LIGHTNING_SENSOR_I2C_BUS` | I2C bus number | `1` | No |
| `LIGHTNING_SENSOR_IRQ_PIN` | BCM GPIO pin for IRQ | `4` | No |
| `LIGHTNING_BUFFER_MAX_SIZE` | Max write buffer size | `10000` | No |
| `LIGHTNING_API_HOST` | REST API bind address | `0.0.0.0` | No |
| `LIGHTNING_API_PORT` | REST API port (1–65535) | `8000` | No |
| `LIGHTNING_CORS_ORIGINS` | Allowed CORS origins (JSON list) | `["*"]` | No |
| `LIGHTNING_DB_POOL_SIZE` | API connection pool size | `5` | No |

#### Example `lightning.toml`

```toml
# Lightning Data Pipeline Configuration

db_host = "192.168.1.100"
db_port = 3306
db_user = "lightning"
db_password = "secret"
db_name = "lightning_events"

# Collector settings
csv_file_path = "/var/lib/lightning/events.csv"
sensor_i2c_address = 3
sensor_i2c_bus = 1
sensor_irq_pin = 4
buffer_max_size = 10000

# API settings
api_host = "0.0.0.0"
api_port = 8000
cors_origins = ["*"]
db_pool_size = 5
```

Place the file in the working directory or set values via environment variables. The file should have restricted permissions (`chmod 0600 lightning.toml`) since it contains credentials.

### System Dependencies

The `mariadb` Python package is a C extension that requires system libraries to compile:

```bash
sudo apt install libmariadb-dev python3-dev
```

> **Note:** If you're using a Python version not provided by the system default (e.g. Python 3.13 from a PPA), install the matching dev package instead: `sudo apt install python3.13-dev`

### Systemd Setup

Unit files are provided in the `systemd/` directory.

```bash
# Install system dependencies
sudo apt install libmariadb-dev python3-dev

# Create service user
sudo useradd -r -s /bin/false lightning

# Create directories
sudo mkdir -p /opt/lightning /var/lib/lightning /etc/lightning
sudo chown lightning:lightning /var/lib/lightning

# Install the package
sudo cp -r . /opt/lightning
cd /opt/lightning
sudo -u lightning python3 -m venv .venv
sudo -u lightning .venv/bin/pip install .

# Create environment file with credentials
sudo tee /etc/lightning/environment << 'EOF'
LIGHTNING_DB_HOST=192.168.1.100
LIGHTNING_DB_PORT=3306
LIGHTNING_DB_USER=lightning
LIGHTNING_DB_PASSWORD=secret
LIGHTNING_DB_NAME=lightning_events
EOF
sudo chmod 0600 /etc/lightning/environment

# Install and enable services
sudo cp systemd/lightning-collector.service /etc/systemd/system/
sudo cp systemd/lightning-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lightning-collector
sudo systemctl enable --now lightning-api
```

Check service status:

```bash
sudo systemctl status lightning-collector
sudo systemctl status lightning-api
sudo journalctl -u lightning-collector -f
sudo journalctl -u lightning-api -f
```

### API Endpoints

The REST API runs on port 8000 by default.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | Paginated list of events with filtering |
| GET | `/events/latest` | Most recent event |
| GET | `/events/stats` | Summary statistics |
| GET | `/health` | Service health check |

#### GET /events

Query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Items per page (max 200) |
| `start_date` | ISO 8601 | — | Filter events after this date |
| `end_date` | ISO 8601 | — | Filter events before this date |
| `event_type` | string | — | Filter by type: `lightning`, `disturber`, or `noise` |

Response includes `data` (list of events) and `pagination` metadata (`total_count`, `page`, `page_size`, `total_pages`). Results are ordered by timestamp descending.

#### GET /events/latest

Returns the most recent event record. Returns HTTP 404 if no events exist.

#### GET /events/stats

Returns summary statistics:
- `count_by_type` — event counts per type (lightning, disturber, noise)
- `count_last_24h` — events in the last 24 hours
- `count_last_7d` — events in the last 7 days
- `latest_event_timestamp` — timestamp of the most recent event (null if none)

#### GET /health

Returns service status, database connectivity, and uptime. Returns HTTP 200 with `"healthy"` when the database is connected, or HTTP 503 with `"degraded"` when the database is unavailable.

### Write Buffer (Network Resilience)

The Collector Service uses an in-memory write buffer (`collections.deque`) to handle transient network failures gracefully. When the MariaDB connection is unavailable, events are buffered locally (up to 10,000 records) and flushed in chronological order once the connection is restored. The collector attempts reconnection every 10 seconds. If the buffer reaches capacity, the oldest record is discarded to make room for new events. CSV writes always happen first, ensuring a reliable local backup regardless of network state.

## License

MIT License — see [LICENSE](LICENSE)

## Credits

- Original library by TangJie (jie.Tang@dfrobot.com), DFRobot, 2019
- Modernization by Christian Kanzler, 2025
- [DFRobot Product Page](https://www.dfrobot.com/product-1828.html)
- [DFRobot Wiki](https://wiki.dfrobot.com/Gravity:%20Lightning%20Sensor%20SKU:%20sen0290)
