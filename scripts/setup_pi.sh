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
#   --install-services                    Install and enable systemd units (collector, API)
#   --service-user NAME                   System user to run services (default: lightning)
#   --env-file PATH                       Environment file for services (default: /etc/lightning/environment)
#   --workdir PATH                        Working directory for services (default: /opt/lightning)
#   --db-wizard                           Interactive database setup (local or remote)
#   --db-apply                            Non-interactive: read env file, init schema, verify connectivity
#   -h, --help                            Show help
set -euo pipefail

# -------- Styling & progress helpers --------
ENABLE_COLOR=1
if [[ -n "${NO_COLOR:-}" || ! -t 1 ]] || ! command -v tput >/dev/null 2>&1; then ENABLE_COLOR=0; fi
if [[ $ENABLE_COLOR -eq 1 ]]; then
  BOLD=$'\e[1m'; DIM=$'\e[2m'; RESET=$'\e[0m';
  RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; CYAN=$'\e[36m';
  CHECK="${GREEN}✔${RESET}"; ARROW="${CYAN}➜${RESET}";
else
  BOLD=""; DIM=""; RESET=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; CHECK="[OK]"; ARROW=">";
fi

STEP=0; TOTAL=0
step() {
  STEP=$((STEP+1))
  printf "${BOLD}%s [%d/%d] %s${RESET}\n" "$ARROW" "$STEP" "$TOTAL" "$1"
}
warn() { printf "%b%s%b\n" "$YELLOW" "$1" "$RESET" >&2; }
die()  { printf "%b%s%b\n" "$RED" "$1" "$RESET" >&2; exit 1; }

# Run pytest, capture final summary line, and fail with message on error.
run_tests() {
  local label="$1"; local outvar="$2"; shift 2
  local outfile
  outfile=$(mktemp)
  pytest -q "$@" 2>&1 | tee "$outfile"
  local code=${PIPESTATUS[0]}
  local summary
  summary=$(grep -E "(^[0-9]+ (passed|failed|skipped|xfailed|xpassed|warnings).*)|(=+ .* in .* =+)" "$outfile" | tail -n1 || true)
  declare -g "$outvar"="${summary:-no summary}"
  if [[ $code -ne 0 ]]; then
    die "$label failed: ${summary:-see pytest output}"
  fi
}

# Prompt helper with default
prompt() {
  local msg="$1"; shift
  local def="$1"; shift || true
  local var
  read -r -p "$msg [${def}]: " var || true
  if [[ -z "$var" ]]; then echo "$def"; else echo "$var"; fi
}

prompt_secret() {
  local msg="$1"; local val
  read -r -s -p "$msg: " val; echo; echo "$val"
}

db_wizard() {
  step "Database setup wizard"

  # Ask local or remote
  local mode
  while true; do
    mode=$(prompt "Setup database on this Pi (local) or use remote host? (local/remote)" "local")
    [[ "$mode" == "local" || "$mode" == "remote" ]] && break
    warn "Please enter 'local' or 'remote'"
  done

  local host port db user pass
  if [[ "$mode" == "local" ]]; then
    host=$(prompt "DB host" "127.0.0.1")
    port=$(prompt "DB port" "3306")
    db=$(prompt "Database name" "lightning")
    user=$(prompt "Database user" "lightning")
    pass=$(prompt_secret "Database password for user '$user'")

    if [[ $DO_APT -eq 1 ]]; then
      step "Installing MariaDB server and client (local)"
      if ! sudo apt-get install -y mariadb-server mariadb-client libmariadb-dev; then
        warn "apt install mariadb-server failed; continuing"
      fi
      sudo systemctl enable --now mariadb || true
    fi

    # Escape single quotes in password for SQL literals
    esc_pass=${pass//\'/''}

    step "Creating database and user via root socket auth"
    TMP_SQL=$(mktemp)
    {
      printf "CREATE DATABASE IF NOT EXISTS \`%s\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n" "$db"
      printf "CREATE USER IF NOT EXISTS '%s'@'localhost' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "CREATE USER IF NOT EXISTS '%s'@'127.0.0.1' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "CREATE USER IF NOT EXISTS '%s'@'::1' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "ALTER USER '%s'@'localhost' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "ALTER USER '%s'@'127.0.0.1' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "ALTER USER '%s'@'::1' IDENTIFIED BY '%s';\n" "$user" "$esc_pass"
      printf "GRANT ALL PRIVILEGES ON \`%s\`.* TO '%s'@'localhost';\n" "$db" "$user"
      printf "GRANT ALL PRIVILEGES ON \`%s\`.* TO '%s'@'127.0.0.1';\n" "$db" "$user"
      printf "GRANT ALL PRIVILEGES ON \`%s\`.* TO '%s'@'::1';\n" "$db" "$user"
      printf "FLUSH PRIVILEGES;\n"
    } > "$TMP_SQL"
    sudo mysql -u root < "$TMP_SQL" || { rm -f "$TMP_SQL"; die "Failed to create database/user via mysql root"; }
    rm -f "$TMP_SQL"

  else
    host=$(prompt "DB host (remote)" "db.example.local")
    port=$(prompt "DB port" "3306")
    db=$(prompt "Database name" "lightning")
    user=$(prompt "Database user (must exist or have create privileges)" "lightning")
    pass=$(prompt_secret "Database password for user '$user'")
  fi

  # Persist env (systemd-safe quoting: escape %, \ and ")
  step "Writing service environment file"
  sudo mkdir -p "$(dirname "$ENV_FILE")"
  _sdq() { local s="$1"; s="${s//%/%%}"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }
  TMP_ENV=$(mktemp)
  {
    printf 'LIGHTNING_DB_HOST="%s"\n' "$(_sdq "$host")"
    printf 'LIGHTNING_DB_PORT=%s\n' "$port"
    printf 'LIGHTNING_DB_USER="%s"\n' "$(_sdq "$user")"
    printf 'LIGHTNING_DB_PASSWORD="%s"\n' "$(_sdq "$pass")"
    printf 'LIGHTNING_DB_NAME="%s"\n' "$(_sdq "$db")"
    printf 'LIGHTNING_CSV_FILE_PATH="%s"\n' "/var/lib/lightning/events.csv"
  } > "$TMP_ENV"
  sudo mv "$TMP_ENV" "$ENV_FILE"
  sudo chmod 640 "$ENV_FILE"

  # Export the same values for immediate use in the following Python steps
  export LIGHTNING_DB_HOST="$host"
  export LIGHTNING_DB_PORT="$port"
  export LIGHTNING_DB_USER="$user"
  export LIGHTNING_DB_PASSWORD="$pass"
  export LIGHTNING_DB_NAME="$db"

  # Initialize schema using project helper
  step "Initializing database schema (events table)"
  python - <<PY || die "Schema initialization failed"
import os
import sys
from lightning_common.db import get_connection, create_tables_if_not_exist

host=os.environ.get('LIGHTNING_DB_HOST','127.0.0.1')
port=int(os.environ.get('LIGHTNING_DB_PORT','3306'))
user=os.environ.get('LIGHTNING_DB_USER','lightning')
pwd=os.environ.get('LIGHTNING_DB_PASSWORD','changeme')
db=os.environ.get('LIGHTNING_DB_NAME','lightning')

try:
    conn=get_connection(host=host,port=port,user=user,password=pwd,database=db)
    create_tables_if_not_exist(conn)
    cur=conn.cursor(); cur.execute('SELECT COUNT(*) FROM events'); cur.fetchone(); cur.close()
    conn.close()
    print('DB OK: schema ensured and reachable')
except Exception as e:
    print('DB ERROR:', e)
    sys.exit(1)
PY

  step "Verifying connectivity with service env"
  python - <<PY || die "Connectivity check failed"
import os, sys
import mariadb
try:
    conn=mariadb.connect(
        host=os.getenv('LIGHTNING_DB_HOST'),
        port=int(os.getenv('LIGHTNING_DB_PORT','3306')),
        user=os.getenv('LIGHTNING_DB_USER'),
        password=os.getenv('LIGHTNING_DB_PASSWORD'),
        database=os.getenv('LIGHTNING_DB_NAME'),
    )
    cur=conn.cursor(); cur.execute('SELECT 1'); cur.fetchone(); cur.close(); conn.close()
    print('Connection OK')
except Exception as e:
    print('Connection ERROR:', e)
    sys.exit(1)
PY

  printf "%s Database setup completed for %s@%s/%s\n" "$CHECK" "$user" "$host" "$db"
}

db_apply() {
  step "Applying DB schema and verifying connectivity from env file"
  if [[ ! -f "$ENV_FILE" ]]; then
    die "Env file not found: $ENV_FILE (use --db-wizard first or create it)"
  fi

  # shellcheck disable=SC2046
  set -a
  # Only export lines that look like KEY=VAL without spaces and not comments
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      eval "$line"
    fi
  done < "$ENV_FILE"
  set +a

  : "${LIGHTNING_DB_HOST:?missing}"
  : "${LIGHTNING_DB_PORT:?missing}"
  : "${LIGHTNING_DB_USER:?missing}"
  : "${LIGHTNING_DB_PASSWORD:?missing}"
  : "${LIGHTNING_DB_NAME:?missing}"

  python - <<'PY' || die "DB apply failed"
import os, sys
from lightning_common.db import get_connection, create_tables_if_not_exist

host=os.getenv('LIGHTNING_DB_HOST')
port=int(os.getenv('LIGHTNING_DB_PORT','3306'))
user=os.getenv('LIGHTNING_DB_USER')
pwd=os.getenv('LIGHTNING_DB_PASSWORD')
db=os.getenv('LIGHTNING_DB_NAME')

try:
    conn=get_connection(host=host,port=port,user=user,password=pwd,database=db)
    create_tables_if_not_exist(conn)
    cur=conn.cursor(); cur.execute('SELECT COUNT(*) FROM events'); count=cur.fetchone()[0]; cur.close()
    conn.close()
    print(f"DB OK: schema ensured and reachable; events rows={count}")
except Exception as e:
    print('DB ERROR:', e)
    sys.exit(1)
PY
}

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
INSTALL_SERVICES=0
SERVICE_USER="lightning"
SERVICE_USER_EXPLICIT=0
ENV_FILE="/etc/lightning/environment"
WORKDIR="/opt/lightning"
DB_WIZARD=0
DB_APPLY=0

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
    --install-services) INSTALL_SERVICES=1; shift ;;
    --service-user) SERVICE_USER="$2"; SERVICE_USER_EXPLICIT=1; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --workdir) WORKDIR="$2"; shift 2 ;;
    --db-wizard) DB_WIZARD=1; shift ;;
    --db-apply) DB_APPLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

# Resolve repo root relative to this script
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

# Compute total steps dynamically now that flags are parsed
TOTAL=5
[[ $RUN_TESTS -eq 1 ]] && TOTAL=$((TOTAL+1))
[[ $RUN_HW -eq 1 ]] && TOTAL=$((TOTAL+1))
[[ $INSTALL_SERVICES -eq 1 ]] && TOTAL=$((TOTAL+1))
[[ $DB_WIZARD -eq 1 ]] && TOTAL=$((TOTAL+1))
[[ $DB_APPLY -eq 1 ]] && TOTAL=$((TOTAL+1))

step "Verifying prerequisites"
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
    step "Enabling I2C via raspi-config (non-interactive)"
    sudo raspi-config nonint do_i2c 0 || echo "raspi-config I2C enable step returned non-zero; attempting fallback"
  else
    step "raspi-config not found; attempting config.txt fallback"
    enable_i2c_fallback || true
  fi
else
  step "Skipping I2C enable per flag"
fi

if [[ $DO_APT -eq 1 ]]; then
  step "Installing OS packages (python3-venv, i2c-tools, pin factory)"
  # Be tolerant of third-party repo signature issues; warn and continue so
  # Debian main packages can still be installed.
  if ! sudo apt-get update -y; then
    warn "'apt-get update' returned an error (possibly due to a third-party repo). Continuing..."
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
      printf "%s\n" "Using gpiozero NativeFactory (no extra packages)"
      ;;
    *) echo "Invalid --pin-factory value: $PIN_FACTORY" >&2; exit 1 ;;
  esac
else
  step "Skipping apt per flag"
fi

if [[ $DO_PROFILE -eq 1 ]]; then
  if [[ "$PIN_FACTORY" == "pigpio" ]]; then
    step "Setting GPIOZERO_PIN_FACTORY globally to pigpio"
    printf '%s\n' 'export GPIOZERO_PIN_FACTORY=pigpio' | sudo tee /etc/profile.d/gpiozero.sh >/dev/null || true
  elif [[ "$PIN_FACTORY" == "lgpio" ]]; then
    step "Setting GPIOZERO_PIN_FACTORY globally to lgpio"
    printf '%s\n' 'export GPIOZERO_PIN_FACTORY=lgpio' | sudo tee /etc/profile.d/gpiozero.sh >/dev/null || true
  else
    step "Not modifying /etc/profile.d for NativeFactory"
  fi
else
  step "Skipping /etc/profile.d changes per flag"
fi

step "Creating venv and installing project + tests"
mkdir -p "$(dirname "$VENV_PATH")"
if [[ ! -x "$VENV_PATH/bin/python" ]]; then
  # Include system site-packages so apt-installed GPIO backends (python3-pigpio,
  # python3-lgpio) are visible inside the venv on Raspberry Pi / Debian.
  python3 -m venv --system-site-packages "$VENV_PATH"
fi
# shellcheck disable=SC1090
source "$VENV_PATH/bin/activate"
pip install -U pip setuptools wheel
cd "$REPO_DIR"
pip install -e '.[test]'
# FastAPI tests require httpx explicitly
pip install httpx

# Ensure selected gpiozero backend is importable in this venv.
if [[ "$PIN_FACTORY" == "pigpio" ]]; then
  if ! python -c "import pigpio" >/dev/null 2>&1; then
    warn "Python module 'pigpio' not found in venv; attempting pip install pigpio"
    pip install pigpio || die "Failed to install 'pigpio'. Install python3-pigpio system package or rerun with --pin-factory lgpio/native."
  fi
elif [[ "$PIN_FACTORY" == "lgpio" ]]; then
  if ! python -c "import lgpio" >/dev/null 2>&1; then
    warn "Python module 'lgpio' not found in venv; attempting pip install lgpio"
    pip install lgpio || die "Failed to install 'lgpio'. Install python3-lgpio system package or rerun with --pin-factory pigpio/native."
  fi
fi

# Create CSV directory (optional but useful for collector)
sudo mkdir -p /var/lib/lightning
sudo chown "$USER":"$USER" /var/lib/lightning || true

MOCK_SUMMARY=""; HW_SUMMARY=""
if [[ $RUN_TESTS -eq 1 ]]; then
  step "Running mocked test suite"
  run_tests "Mocked tests" MOCK_SUMMARY
fi

if [[ $RUN_HW -eq 1 ]]; then
  step "Running hardware smoke test"
  export AS3935_TEST_REAL_HARDWARE=1
  export AS3935_I2C_ADDRESS="$ADDR"
  export AS3935_I2C_BUS="$BUS"
  export AS3935_IRQ_PIN="$IRQ"
  run_tests "Hardware tests" HW_SUMMARY -m hardware
fi

if [[ $DB_WIZARD -eq 1 ]]; then
  db_wizard
fi

if [[ $DB_APPLY -eq 1 ]]; then
  db_apply
fi

if [[ $INSTALL_SERVICES -eq 1 ]]; then
  step "Installing and enabling systemd services"

  require_cmd systemctl
  # Ensure service user and basic directories exist
  if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    sudo useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER" || true
  fi
  sudo mkdir -p "$(dirname "$ENV_FILE")" "$WORKDIR" /var/lib/lightning
  sudo touch "$ENV_FILE"
  sudo chown "$SERVICE_USER":"$SERVICE_USER" /var/lib/lightning || true
  sudo chown root:root "$(dirname "$ENV_FILE")" || true

  # Write a template env file if empty
  if [[ ! -s "$ENV_FILE" ]]; then
    TMP_ENV=$(mktemp)
    cat > "$TMP_ENV" <<EOF
# Lightning services environment
# Edit these values to match your MariaDB and file locations.
LIGHTNING_DB_HOST="127.0.0.1"
LIGHTNING_DB_PORT=3306
LIGHTNING_DB_USER="lightning"
LIGHTNING_DB_PASSWORD="changeme"
LIGHTNING_DB_NAME="lightning"
LIGHTNING_CSV_FILE_PATH="/var/lib/lightning/events.csv"

# Pin factory for gpiozero (pigpio recommended if installed)
GPIOZERO_PIN_FACTORY=${PIN_FACTORY}
EOF
    sudo mv "$TMP_ENV" "$ENV_FILE"
    sudo chmod 640 "$ENV_FILE"
  fi

  # Resolve venv python path for ExecStart
  VENV_PY="$VENV_PATH/bin/python"
  if [[ ! -x "$VENV_PY" ]]; then
    echo "Venv python not found at $VENV_PY" >&2; exit 1
  fi

  # Ensure selected service user can execute the venv python. Common failure:
  # dedicated user cannot traverse /home/<user>/... venv paths.
  if ! sudo -u "$SERVICE_USER" test -x "$VENV_PY" >/dev/null 2>&1; then
    if [[ $SERVICE_USER_EXPLICIT -eq 1 ]]; then
      die "Service user '$SERVICE_USER' cannot execute '$VENV_PY'. Use --service-user '$USER' or set --venv-path to a location accessible by '$SERVICE_USER' (e.g. /opt/lightning/.venv)."
    else
      warn "Service user '$SERVICE_USER' cannot execute '$VENV_PY'; switching service user to '$USER' for compatibility."
      SERVICE_USER="$USER"
    fi
  fi

  # Generate unit files with explicit venv python and pigpio dependency if selected
  UNIT_DIR=/etc/systemd/system
  TMP_API=$(mktemp)
  TMP_COL=$(mktemp)
  AFTER_NET="After=network-online.target"
  WANTS_NET="Wants=network-online.target"
  PIGPIO_DEPS=""
  if [[ "$PIN_FACTORY" == "pigpio" ]]; then
    PIGPIO_DEPS=$'Wants=pigpiod.service\nAfter=pigpiod.service'
  fi

  # One-shot DB apply unit to ensure schema before API/Collector start
  TMP_DB=$(mktemp)
  cat > "$TMP_DB" <<EOF
[Unit]
Description=Lightning DB Initialize (one-shot)
$AFTER_NET
$WANTS_NET

[Service]
Type=oneshot
ExecStart=$VENV_PY -m lightning_common.cli_db_apply
EnvironmentFile=$ENV_FILE
WorkingDirectory=$WORKDIR
User=$SERVICE_USER
Group=$SERVICE_USER
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

  cat > "$TMP_API" <<EOF
[Unit]
Description=Lightning REST API Service
$AFTER_NET
$WANTS_NET
$PIGPIO_DEPS
Wants=lightning-db-apply.service
After=lightning-db-apply.service

[Service]
Type=simple
ExecStart=$VENV_PY -m lightning_api
Restart=on-failure
RestartSec=5
EnvironmentFile=$ENV_FILE
WorkingDirectory=$WORKDIR
User=$SERVICE_USER
Group=$SERVICE_USER

[Install]
WantedBy=multi-user.target
EOF

  cat > "$TMP_COL" <<EOF
[Unit]
Description=Lightning Data Collector Service
$AFTER_NET
$WANTS_NET
$PIGPIO_DEPS
Wants=lightning-db-apply.service
After=lightning-db-apply.service

[Service]
Type=simple
ExecStart=$VENV_PY -m lightning_collector
Restart=on-failure
RestartSec=5
EnvironmentFile=$ENV_FILE
WorkingDirectory=$WORKDIR
User=$SERVICE_USER
Group=$SERVICE_USER

[Install]
WantedBy=multi-user.target
EOF

  sudo mv "$TMP_DB" "$UNIT_DIR/lightning-db-apply.service"
  sudo mv "$TMP_API" "$UNIT_DIR/lightning-api.service"
  sudo mv "$TMP_COL" "$UNIT_DIR/lightning-collector.service"
  sudo chmod 644 "$UNIT_DIR/lightning-db-apply.service" "$UNIT_DIR/lightning-api.service" "$UNIT_DIR/lightning-collector.service"

  sudo systemctl daemon-reload
  sudo systemctl enable --now lightning-db-apply.service || true
  sudo systemctl enable --now lightning-collector.service || true
  sudo systemctl enable --now lightning-api.service || true

  printf "%s Services installed: lightning-collector, lightning-api\n" "$CHECK"
  printf "%s\n" "Edit $ENV_FILE to adjust DB and GPIO settings, then restart:"
  printf "  %s\n" "sudo systemctl restart lightning-collector lightning-api"
fi

echo
if [[ $RUN_TESTS -eq 1 || $RUN_HW -eq 1 ]]; then
  printf "${BOLD}Tests complete.${RESET}\n"
  [[ $RUN_TESTS -eq 1 ]] && echo "  Mocked:   ${MOCK_SUMMARY}"
  [[ $RUN_HW -eq 1 ]] && echo "  Hardware: ${HW_SUMMARY}"
  echo
fi

printf "${BOLD}Setup complete.${RESET}\n"
echo "  1) Reboot once if you just enabled I2C or installed pigpio: sudo reboot"
echo "  2) Activate venv:  source '$VENV_PATH/bin/activate'"
echo "  3) Run example:   python examples/lightning_detection.py"
echo "  4) Optional HIL:  AS3935_TEST_REAL_HARDWARE=1 pytest -q -m hardware"
