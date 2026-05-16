#!/usr/bin/env bash
# Raspberry Pi Zero 2W setup for DFRobot_AS3935
# - Enables I2C, installs dependencies, configures a GPIO pin factory
# - Creates a Python venv, installs the project (editable) + test deps
# - Optional: runs mocked tests and/or hardware smoke test
#
# Usage (quick):
#   bash scripts/setup_pi.sh --run-tests --hardware-tests
#
# Options:
#   --pin-factory [pigpio|lgpio|native]   Default: pigpio
#   --venv-path PATH                      Default: ~/.venvs/DFRobot_AS3935
#   --skip-apt                            Skip apt operations
#   --no-profile                          Do not write /etc/profile.d env file
#   --no-i2c                              Skip raspi-config I2C enable step
#   --run-tests                           Run full mocked test suite
#   --hardware-tests                      Run opt-in hardware smoke test
#   --address HEX                         I2C address for hardware test (default 0x03)
#   --bus NUM                             I2C bus for hardware test (default 1)
#   --irq NUM                             BCM IRQ pin for hardware test (default 4)
#   -h, --help                            Show help
set -euo pipefail

PIN_FACTORY="pigpio"
VENV_PATH="${HOME}/.venvs/DFRobot_AS3935"
DO_APT=1
DO_PROFILE=1
DO_I2C=1
RUN_TESTS=0
RUN_HW=0
ADDR="0x03"
BUS="1"
IRQ="4"

usage() {
  sed -n '1,40p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pin-factory) PIN_FACTORY="$2"; shift 2 ;;
    --venv-path) VENV_PATH="$2"; shift 2 ;;
    --skip-apt) DO_APT=0; shift ;;
    --no-profile) DO_PROFILE=0; shift ;;
    --no-i2c) DO_I2C=0; shift ;;
    --run-tests) RUN_TESTS=1; shift ;;
    --hardware-tests) RUN_HW=1; shift ;;
    --address) ADDR="$2"; shift 2 ;;
    --bus) BUS="$2"; shift 2 ;;
    --irq) IRQ="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# Resolve repo root relative to this script
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

echo "[1/6] Verifying prerequisites"
require_cmd python3
require_cmd git
if [[ $DO_APT -eq 1 ]]; then
  require_cmd sudo
  require_cmd apt-get
fi

enable_i2c_fallback() {
  # Try to enable I2C by editing firmware config directly when raspi-config is absent.
  # Supports both Raspberry Pi OS (/boot/config.txt) and Debian on Pi (/boot/firmware/config.txt).
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    if [[ -w "$cfg" || -w "${cfg}" ]]; then
      echo "Attempting to enable I2C in $cfg"
      sudo cp -n "$cfg" "${cfg}.bak" 2>/dev/null || true
      if sudo grep -qE '^\s*dtparam=([^,]*,)*i2c_arm=on(,.*)?\s*$' "$cfg" 2>/dev/null; then
        echo "I2C already enabled in $cfg"
        return
      fi
      if sudo grep -qE '^\s*dtparam=([^,]*,)*i2c_arm=off(,.*)?\s*$' "$cfg" 2>/dev/null; then
        sudo sed -i 's/\(dtparam=.*\)i2c_arm=off/\1i2c_arm=on/' "$cfg" || true
      else
        echo 'dtparam=i2c_arm=on' | sudo tee -a "$cfg" >/dev/null || true
      fi
      echo "I2C enable flag written to $cfg (reboot required)"
      return
    fi
  done
  echo "Could not locate a writable config.txt to enable I2C; please enable manually." >&2
}

if [[ $DO_I2C -eq 1 ]]; then
  if command -v raspi-config >/dev/null 2>&1; then
    echo "[2/6] Enabling I2C via raspi-config (non-interactive)"
    sudo raspi-config nonint do_i2c 0 || echo "raspi-config I2C enable step returned non-zero; attempting fallback"
  else
    echo "[2/6] raspi-config not found; attempting config.txt fallback"
    enable_i2c_fallback || true
  fi
else
  echo "[2/6] Skipping I2C enable per flag"
fi

if [[ $DO_APT -eq 1 ]]; then
  echo "[3/6] Installing OS packages (python3-venv, i2c-tools, pin factory)"
  # Be tolerant of third-party repo signature issues; warn and continue so
  # Debian main packages can still be installed.
  if ! sudo apt-get update -y; then
    echo "WARNING: 'apt-get update' returned an error (possibly due to a third-party repo). Continuing anyway..." >&2
  fi
  sudo apt-get install -y python3-venv i2c-tools
  case "$PIN_FACTORY" in
    pigpio)
      sudo apt-get install -y pigpio python3-pigpio
      sudo systemctl enable --now pigpiod || true
      ;;
    lgpio)
      sudo apt-get install -y python3-lgpio
      ;;
    native)
      echo "Using gpiozero NativeFactory (no extra packages)"
      ;;
    *) echo "Invalid --pin-factory value: $PIN_FACTORY" >&2; exit 1 ;;
  esac
else
  echo "[3/6] Skipping apt per flag"
fi

if [[ $DO_PROFILE -eq 1 ]]; then
  if [[ "$PIN_FACTORY" == "pigpio" ]]; then
    echo "[4/6] Setting GPIOZERO_PIN_FACTORY globally to pigpio"
    printf '%s\n' 'export GPIOZERO_PIN_FACTORY=pigpio' | sudo tee /etc/profile.d/gpiozero.sh >/dev/null || true
  elif [[ "$PIN_FACTORY" == "lgpio" ]]; then
    echo "[4/6] Setting GPIOZERO_PIN_FACTORY globally to lgpio"
    printf '%s\n' 'export GPIOZERO_PIN_FACTORY=lgpio' | sudo tee /etc/profile.d/gpiozero.sh >/dev/null || true
  else
    echo "[4/6] Not modifying /etc/profile.d for NativeFactory"
  fi
else
  echo "[4/6] Skipping /etc/profile.d changes per flag"
fi

echo "[5/6] Creating venv and installing project + tests"
mkdir -p "$(dirname "$VENV_PATH")"
python3 -m venv "$VENV_PATH" || true
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
pip install -U pip setuptools wheel
cd "$REPO_DIR"
pip install -e '.[test]'
# FastAPI tests require httpx explicitly
pip install httpx

# Create CSV directory (optional but useful for collector)
sudo mkdir -p /var/lib/lightning
sudo chown "$USER":"$USER" /var/lib/lightning || true

if [[ $RUN_TESTS -eq 1 ]]; then
  echo "[6/6] Running mocked test suite"
  pytest -q || { echo "Mocked tests failed" >&2; exit 1; }
fi

if [[ $RUN_HW -eq 1 ]]; then
  echo "[6/6] Running hardware smoke test"
  export AS3935_TEST_REAL_HARDWARE=1
  export AS3935_I2C_ADDRESS="$ADDR"
  export AS3935_I2C_BUS="$BUS"
  export AS3935_IRQ_PIN="$IRQ"
  pytest -q -m hardware || { echo "Hardware smoke test failed" >&2; exit 1; }
fi

echo
echo "Setup complete. Next steps:"
echo "  1) Reboot once if you just enabled I2C or installed pigpio: sudo reboot"
echo "  2) Activate venv:  source '$VENV_PATH/bin/activate'"
echo "  3) Run example:   python examples/lightning_detection.py"
echo "  4) Optional HIL:  AS3935_TEST_REAL_HARDWARE=1 pytest -q -m hardware"
