# DFRobot AS3935 — Out-of-the-Box Guide for Beginners

This guide walks you through setting up the AS3935 Lightning Sensor on a fresh Raspberry Pi from start to finish. Choose your deployment method:

- **Method A: Docker (Recommended)** — Fastest, containerized, easier to manage
- **Method B: Native systemd** — Direct system integration, slightly more setup

Both methods are fully tested on:
- Raspberry Pi 4B (8GB)
- Raspberry Pi 5 (8GB)
- Raspberry Pi Zero 2W

---

## Prerequisites

### What you'll need

| Item | Notes |
|------|-------|
| Raspberry Pi (4B/5/Zero 2W) | Pi 4/5 recommended for better performance |
| microSD card (16GB+) | Raspberry Pi OS will be installed here |
| USB-C power supply (5V/3A for Pi 4/5, 2.5A for Zero 2W) | Official Raspberry Pi supply recommended |
| AS3935 Lightning Sensor | SEN0290 from DFRobot |
| Jumper wires (Female-to-Female) | For connecting to GPIO header |
| Internet connection | For downloading packages and Docker images |

---

## Step 0: Install Raspberry Pi OS

### Download and flash the OS

1. **Download Raspberry Pi Imager**
   - Windows/macOS: https://www.raspberrypi.com/software/
   - Already installed on Raspberry Pi OS? Skip this step

2. **Insert microSD card** into your computer

3. **Open Raspberry Pi Imager**
   - Click **CHOOSE OS** → **Raspberry Pi OS (Other)** → **Raspberry Pi OS Lite** (64-bit, no desktop, smallest footprint)
   - **Alternative**: Choose **Raspberry Pi OS** → **Raspberry Pi OS (64-bit)** if you want a desktop environment

4. **Click CHOOSE STORAGE** → Select your microSD card

5. **Click SAVE** → Wait for the image to flash (5-10 minutes)

### First boot configuration

1. **Insert the microSD card** into your Raspberry Pi

2. **Connect peripherals**:
   - USB-C power cable
   - Monitor via HDMI
   - Keyboard via USB
   - (Pi Zero 2W: You'll need a USB OTG adapter for keyboard, or SSH from another machine)

3. **Power on** the Pi

4. **Follow the setup wizard**:
   - Select language, timezone, Wi-Fi network
   - Create a user account (e.g., `pi` / `lightning`)
   - Let the system update

5. **After setup completes**, open a terminal and run:

```bash
# Update package lists
sudo apt update

# Upgrade installed packages (optional, but recommended)
sudo apt upgrade -y

# Reboot if the kernel was updated
sudo reboot
```

---

## Step 1: Wire the AS3935 Sensor

### GPIO Pinout Reference

| Raspberry Pi Pin | BCM Number | Function |
|-----------------|------------|----------|
| Pin 1 | 3.3V | Power (3.3V) |
| Pin 6 | GND | Ground |
| Pin 3 | GPIO 2 (SDA1) | I2C Data |
| Pin 5 | GPIO 3 (SCL1) | I2C Clock |
| Pin 7 | GPIO 4 | Interrupt (IRQ) |

### Wiring Diagram

```
AS3935 Sensor        Raspberry Pi
---------------      ------------
VCC (3.3V)  ──────── Pin 1 (3.3V)
GND         ──────── Pin 6 (GND)
SDA         ──────── Pin 3 (GPIO 2, SDA1)
SCL         ──────── Pin 5 (GPIO 3, SCL1)
IRQ         ──────── Pin 7 (GPIO 4)
```

### Enable I2C Interface

The sensor communicates via I2C, which must be enabled first:

```bash
# Open the configuration tool
sudo raspi-config

# Navigate: Interface Options → I2C → Enable
# Navigate: Interface Options → SPI → Enable (optional, not used but harmless)

# Exit raspi-config and reboot
sudo reboot
```

### Verify I2C Hardware

After reboot, verify I2C is working:

```bash
# Load I2C kernel modules
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835

# Install I2C tools (if not already installed)
sudo apt install -y i2c-tools

# Scan for I2C devices (should show the sensor at address 0x03)
sudo i2cdetect -y 1
```

Expected output (sensor at address 0x03):

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- 3U -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

Note `3U` at address `0x03`. If you see a different address, adjust the `LIGHTNING_SENSOR_I2C_ADDRESS` in the configuration.

---

## Method A: Docker Deployment (Recommended)

### Install Docker

The setup script automates Docker installation and configuration:

```bash
# Navigate to the project directory (or clone if not done yet)
cd ~
git clone https://github.com/DFRobot/DFRobot_AS3935.git
cd DFRobot_AS3935

# Run the setup script (will prompt to install Docker if needed)
bash docker/setup.sh
```

The script will:
- Check for Docker, Docker Compose, I2C kernel modules
- Offer to install missing components
- Detect I2C/GPIO group IDs
- Create `.env` from `.env.sample` with auto-detected GIDs

### Configure Environment Variables

Edit `.env` with your MariaDB credentials:

```bash
nano .env
```

Required values:

```env
# MariaDB configuration
MARIADB_ROOT_PASSWORD=changeme-root          # Change this!
LIGHTNING_DB_PASSWORD=changeme                # Change this too!

# Database connection (use 'mariadb' for Docker service name)
LIGHTNING_DB_HOST=mariadb
LIGHTNING_DB_USER=lightning
LIGHTNING_DB_NAME=lightning_events
```

Optional (add at the bottom if not present):

```env
# Sensor configuration
LIGHTNING_SENSOR_I2C_ADDRESS=3                # 0x03 (DIP switch setting)
LIGHTNING_SENSOR_I2C_BUS=1                    # I2C bus 1
LIGHTNING_SENSOR_IRQ_PIN=4                    # BCM 4 (GPIO 4, Pin 7)

# API configuration
LIGHTNING_API_HOST=0.0.0.0
LIGHTNING_API_PORT=8000
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

### Start the Services

```bash
# Build the Docker image (first time only)
docker compose build

# Start all services in background
docker compose up -d

# Check status
docker compose ps
```

Expected output:

```
NAME                      COMMAND                  SERVICE             STATUS
dfrobot-as3935-db-init-1  "/opt/venv/bin/pytho…"   db-init             exited (0)
dfrobot-as3935-lightni…   "/opt/venv/bin/pytho…"   lightning-api       running
dfrobot-as3935-mariadb-1  "/docker-entrypoint.…"   mariadb             running
```

### Verify the API is Working

```bash
# Health check
curl http://127.0.0.1:8000/health

# Should return: {"status":"healthy"}
```

---

## Method B: Native Systemd Deployment

### Install System Dependencies

```bash
# Update and upgrade
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3-pip \
    python3-venv \
    libmariadb-dev \
    python3-dev \
    git \
    curl
```

### Clone the Repository

```bash
cd ~
git clone https://github.com/DFRobot/DFRobot_AS3935.git
cd DFRobot_AS3935
```

### Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip and install project
pip install --upgrade pip
pip install .
```

### Configure the Database

Install and configure MariaDB:

```bash
# Install MariaDB
sudo apt install -y mariadb-server

# Run security script
sudo mysql_secure_installation

# Answer the prompts:
# - Enter current password for root: [press Enter if fresh install]
# - Set root password? [Y] → Y
# - New password: [enter strong password]
# - Remove anonymous users? [Y]
# - Disallow root login remotely? [Y]
# - Remove test database? [Y]
# - Reload privilege tables? [Y]
```

Create the database and user:

```bash
sudo mysql <<EOF
CREATE DATABASE lightning_events;
CREATE USER 'lightning'@'localhost' IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON lightning_events.* TO 'lightning'@'localhost';
FLUSH PRIVILEGES;
EOF
```

### Create Environment File

```bash
# Create directory for configuration
sudo mkdir -p /etc/lightning

# Create environment file
sudo tee /etc/lightning/environment >/dev/null <<EOF
LIGHTNING_DB_HOST=127.0.0.1
LIGHTNING_DB_PORT=3306
LIGHTNING_DB_USER=lightning
LIGHTNING_DB_PASSWORD=changeme
LIGHTNING_DB_NAME=lightning_events
LIGHTNING_CSV_FILE_PATH=/var/lib/lightning/events.csv
LIGHTNING_SENSOR_I2C_ADDRESS=3
LIGHTNING_SENSOR_I2C_BUS=1
LIGHTNING_SENSOR_IRQ_PIN=4
LIGHTNING_BUFFER_MAX_SIZE=10000
EOF

# Secure the environment file
sudo chmod 600 /etc/lightning/environment
```

### Create Service User and Directories

```bash
# Create service user (no login shell)
sudo useradd -r -s /bin/false lightning

# Create directories
sudo mkdir -p /opt/lightning /var/lib/lightning /etc/lightning

# Set ownership
sudo chown lightning:lightning /var/lib/lightning

# Copy project files
sudo cp -r . /opt/lightning
cd /opt/lightning

# Create virtual environment for service user
sudo -u lightning python3 -m venv .venv
sudo -u lightning .venv/bin/pip install --upgrade pip
sudo -u lightning .venv/bin/pip install .
```

### Install Systemd Services

```bash
# Copy service files
sudo cp systemd/lightning-collector.service /etc/systemd/system/
sudo cp systemd/lightning-api.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable --now lightning-collector
sudo systemctl enable --now lightning-api
```

### Initialize the Database Schema

```bash
# Run schema initialization
sudo -u lightning /opt/lightning/.venv/bin/python -m lightning_common.cli_db_apply

# Should output: DB OK: schema ensured; rows=0
```

---

## Testing Your Installation

### Quick Sensor Test (Python)

```bash
# Activate virtual environment if using native
source ~/DFRobot_AS3935/.venv/bin/activate

# Run the example script
cd ~/DFRobot_AS3935
python examples/lightning_detection.py
```

Expected behavior:
- Script starts and shows configuration
- Wait for lightning events (sensor detects atmospheric noise initially)
- If you trigger the sensor (e.g., wave hand near it), you should see "Noise!" events
- If a lightning storm approaches, you'll see distance and energy values

### Test the REST API

```bash
# Health check
curl http://127.0.0.1:8000/health

# Get latest event
curl http://127.0.0.1:8000/events/latest

# Get events with pagination
curl "http://127.0.0.1:8000/events?page=1&page_size=5"
```

### View Logs

**Docker method:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f lightning-api
docker compose logs -f lightning-collector
```

**Native systemd method:**
```bash
# View all service logs
sudo journalctl -u lightning-collector -u lightning-api -f

# Follow only collector
sudo journalctl -u lightning-collector -f

# Follow only API
sudo journalctl -u lightning-api -f
```

---

## Troubleshooting

### I2C Device Not Found

```bash
# Check I2C is enabled
sudo raspi-config

# Check kernel modules are loaded
lsmod | grep i2c

# If not loaded:
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835

# Make persistent across reboots:
echo 'i2c-dev' | sudo tee /etc/modules-load.d/i2c.conf
echo 'i2c-bcm2835' | sudo tee -a /etc/modules-load.d/i2c.conf
```

### Permission Denied on /dev/i2c-1

```bash
# Check current permissions
ls -la /dev/i2c-1

# Add user to i2c group
sudo usermod -aG i2c $USER

# Log out and back in for changes to take effect
```

### Database Connection Failed

**Docker:**
```bash
# Check MariaDB is running
docker compose ps mariadb

# Check logs
docker compose logs mariadb

# Verify .env values match:
# LIGHTNING_DB_HOST=mariadb  (NOT 127.0.0.1)
# LIGHTNING_DB_PORT=3306
# LIGHTNING_DB_USER=lightning
# LIGHTNING_DB_PASSWORD=<same as MARIADB_PASSWORD in .env>
```

**Native:**
```bash
# Check MariaDB service
sudo systemctl status mariadb

# Test connection manually
mysql -u lightning -p -h 127.0.0.1 lightning_events

# Check user permissions
sudo mysql -e "SELECT User, Host FROM mysql.user WHERE User='lightning';"
```

### Collector Can't Connect to Sensor

```bash
# Verify I2C address
sudo i2cdetect -y 1

# Expected output shows 3U at 0x03 (or 0x01/0x02 if DIP switch changed)

# Update configuration if address differs:
# In .env: LIGHTNING_SENSOR_I2C_ADDRESS=1 (or 2)
```

### Service Won't Start

**Check logs:**
```bash
# Docker
docker compose logs <service-name>

# Native
sudo journalctl -u <service-name> -n 100
```

**Common causes:**
- Incorrect database credentials in `.env`
- Sensor not connected or wrong I2C address
- GPIO pin already in use by another process

---

## Upgrading

### Docker Method

```bash
# Pull latest changes
cd ~/DFRobot_AS3935
git pull

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d
```

### Native Systemd Method

```bash
cd ~/DFRobot_AS3935

# Stop services
sudo systemctl stop lightning-collector lightning-api

# Backup config
sudo cp /etc/lightning/environment /etc/lightning/environment.bak

# Update project
git pull

# Update virtual environment
source .venv/bin/activate
pip install --upgrade pip
pip install .

# Restart services
sudo systemctl start lightning-api lightning-collector
```

---

## Next Steps

1. **Adjust sensor sensitivity** based on your environment (indoor vs. outdoor)
2. **Set up alerting** — use the REST API to trigger notifications
3. **Add a dashboard** — build a frontend that calls the `/events` endpoint
4. **Monitor logs** — set up log aggregation for long-term analysis

For detailed API documentation, see the main [README.md](README.md) and [API Reference](#api-reference).

---

## Hardware Options

### Sensor DIP Switch Configuration

The AS3935 has a 3-bit DIP switch for the I2C address:

| DIP Switch Setting | I2C Address | LIGHTNING_SENSOR_I2C_ADDRESS |
|-------------------|-------------|------------------------------|
| All OFF (000)     | 0x01        | 1                            |
| A1 ON (001)       | 0x02        | 2                            |
| A2 ON (010)       | 0x03        | 3                            |
| A1+A2 ON (011)    | 0x04        | 4 (not supported)            |

Default is 0x03 (A2 ON). Update `LIGHTNING_SENSOR_I2C_ADDRESS` in `.env` to match.

### Antenna Tuning

The sensor includes an antenna that should be tuned for optimal range:

```bash
# Run the sensor configuration example
cd ~/DFRobot_AS3935
python examples/sensor_configuration.py
```

This script walks you through the tuning process with step-by-step instructions.

---

## Getting Help

- **GitHub Issues**: https://github.com/DFRobot/DFRobot_AS3935/issues
- **DFRobot Product Page**: https://www.dfrobot.com/product-1828.html
- **DFRobot Wiki**: https://wiki.dfrobot.com/Gravity:_Lightning_Sensor_SKU:sen0290

---

## Quick Reference

| Command | Docker | Native |
|---------|--------|--------|
| Start services | `docker compose up -d` | `sudo systemctl start lightning-collector lightning-api` |
| Stop services | `docker compose down` | `sudo systemctl stop lightning-collector lightning-api` |
| Check status | `docker compose ps` | `sudo systemctl status lightning-*` |
| View logs | `docker compose logs -f` | `sudo journalctl -u lightning-* -f` |
| Test API | `curl http://127.0.0.1:8000/health` | Same |
| Test sensor | `python examples/lightning_detection.py` | Same |

---

*This guide was last updated for DFRobot_AS3935 v2.0.0*
