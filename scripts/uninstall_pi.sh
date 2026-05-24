#!/usr/bin/env bash
# Uninstall Lightning services and related files created by scripts/setup_pi.sh
# - Stops and disables systemd units
# - Removes unit files and reloads systemd
# - Optionally removes env file, venv, CSV data directory, and gpiozero profile
#
# Usage:
#   bash scripts/uninstall_pi.sh [--purge] [--yes] [--keep-venv] [--keep-env]
#
# Flags:
#   --purge       Remove venv, env, CSV (no prompts)
#   --yes         Assume 'yes' to all prompts (safer than --purge; still skips non-owned files)
#   --keep-venv   Keep the Python venv even when purging
#   --keep-env    Keep /etc/lightning/environment even when purging
#   --units-only  Only remove systemd units; keep data and env

set -euo pipefail

PURGE=0
ASSUME_YES=0
KEEP_VENV=0
KEEP_ENV=0
UNITS_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE=1; ASSUME_YES=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --keep-venv) KEEP_VENV=1; shift ;;
    --keep-env) KEEP_ENV=1; shift ;;
    --units-only) UNITS_ONLY=1; shift ;;
    -h|--help)
      sed -n '1,80p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Styling
ENABLE_COLOR=1
if [[ -n "${NO_COLOR:-}" || ! -t 1 ]] || ! command -v tput >/dev/null 2>&1; then ENABLE_COLOR=0; fi
if [[ $ENABLE_COLOR -eq 1 ]]; then
  BOLD=$'\e[1m'; RESET=$'\e[0m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; CYAN=$'\e[36m'; RED=$'\e[31m'
  OK="${GREEN}✔${RESET}"; ARROW="${CYAN}➜${RESET}"
else
  BOLD=""; RESET=""; GREEN=""; YELLOW=""; CYAN=""; RED=""; OK="[OK]"; ARROW=">"
fi

say() { printf "%s %s\n" "$ARROW" "$1"; }
warn() { printf "%b%s%b\n" "$YELLOW" "$1" "$RESET" >&2; }
err() { printf "%b%s%b\n" "$RED" "$1" "$RESET" >&2; }
ok() { printf "%b %s\n" "$OK" "$1"; }

confirm() {
  local prompt="$1"; shift
  if [[ $ASSUME_YES -eq 1 ]]; then return 0; fi
  read -r -p "$prompt [y/N]: " ans || true
  [[ "$ans" =~ ^[Yy]([Ee][Ss])?$ ]]
}

# Units we manage
UNITS=(
  "/etc/systemd/system/lightning-api.service"
  "/etc/systemd/system/lightning-collector.service"
  "/etc/systemd/system/lightning-db-apply.service"
)

say "Stopping and disabling services (ignore errors if absent)"
for u in "${UNITS[@]}"; do
  name=$(basename "$u")
  if systemctl list-unit-files | grep -q "^${name}\\."; then
    sudo systemctl stop "$name" || true
    sudo systemctl disable "$name" || true
  fi
done

say "Removing unit files"
for u in "${UNITS[@]}"; do
  if [[ -f "$u" ]]; then sudo rm -f "$u"; fi
done
sudo systemctl daemon-reload || true
ok "Systemd units removed"

if [[ $UNITS_ONLY -eq 1 ]]; then
  ok "Units-only mode complete"
  exit 0
fi

# Try to determine env file, venv path, and working directory from old unit files (if any existed)
ENV_FILE="/etc/lightning/environment"
WORKDIR="/opt/lightning"
VENV_PY=""
for snapshot in \
  "/etc/systemd/system/lightning-api.service" \
  "/etc/systemd/system/lightning-collector.service"; do
  [[ -f "$snapshot" ]] || continue
  # shellcheck disable=SC2002
  ENV_FILE=$(grep -E '^EnvironmentFile=' "$snapshot" | head -n1 | cut -d= -f2- || true)
  WORKDIR=$(grep -E '^WorkingDirectory=' "$snapshot" | head -n1 | cut -d= -f2- || true)
  VENV_PY=$(grep -E '^ExecStart=' "$snapshot" | head -n1 | sed 's/^ExecStart=\([^ ]*\).*/\1/' || true)
done

CSV_PATH=""
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC2046
  CSV_PATH=$(grep -E '^LIGHTNING_CSV_FILE_PATH=' "$ENV_FILE" | sed 's/^LIGHTNING_CSV_FILE_PATH=\"\{0,1\}//; s/\"$//' || true)
fi

# Remove env file
if [[ -f "$ENV_FILE" ]]; then
  if [[ $PURGE -eq 1 && $KEEP_ENV -eq 0 ]] || confirm "Remove env file $ENV_FILE?"; then
    sudo rm -f "$ENV_FILE" || true
    dir=$(dirname "$ENV_FILE")
    # remove dir if empty
    if [[ -d "$dir" ]] && [[ -z "$(ls -A "$dir" 2>/dev/null || true)" ]]; then sudo rmdir "$dir" || true; fi
    ok "Removed env file"
  else
    warn "Kept env file: $ENV_FILE"
  fi
fi

# Remove CSV data file (if exists)
if [[ -n "$CSV_PATH" && -e "$CSV_PATH" ]]; then
  if [[ $PURGE -eq 1 ]] || confirm "Remove CSV data file $CSV_PATH?"; then
    sudo rm -f "$CSV_PATH" || true
    pdir=$(dirname "$CSV_PATH")
    if [[ -d "$pdir" ]] && [[ -z "$(ls -A "$pdir" 2>/dev/null || true)" ]]; then sudo rmdir "$pdir" || true; fi
    ok "Removed CSV data file"
  else
    warn "Kept CSV data file: $CSV_PATH"
  fi
fi

# Remove venv if it looks like our standard path and not explicitly kept
if [[ -n "$VENV_PY" ]]; then
  VENV_DIR=$(dirname "$VENV_PY")/..
  VENV_DIR=$(cd "$VENV_DIR" 2>/dev/null && pwd || true)
  if [[ -n "$VENV_DIR" && -d "$VENV_DIR" ]]; then
    if [[ $KEEP_VENV -eq 1 ]]; then
      warn "Kept venv: $VENV_DIR"
    else
      if [[ $PURGE -eq 1 ]] || confirm "Remove venv $VENV_DIR?"; then
        rm -rf "$VENV_DIR" || sudo rm -rf "$VENV_DIR" || true
        ok "Removed venv"
      else
        warn "Kept venv: $VENV_DIR"
      fi
    fi
  fi
fi

# Remove gpiozero profile file if it only contains our export line
GZ_PROFILE="/etc/profile.d/gpiozero.sh"
if [[ -f "$GZ_PROFILE" ]]; then
  if grep -q '^export GPIOZERO_PIN_FACTORY=' "$GZ_PROFILE" && [[ $(wc -l < "$GZ_PROFILE") -le 2 ]]; then
    if [[ $PURGE -eq 1 ]] || confirm "Remove $GZ_PROFILE?"; then
      sudo rm -f "$GZ_PROFILE" || true
      ok "Removed $GZ_PROFILE"
    fi
  fi
fi

ok "Uninstall complete"
printf "${BOLD}Next steps:${RESET}\n"
echo "  - If you no longer need MariaDB locally: sudo apt remove --purge mariadb-server mariadb-client"
echo "  - Remove leftover directories if desired (e.g., /opt/lightning)"
