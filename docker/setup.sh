#!/usr/bin/env bash
# =============================================================================
# Lightning Data Pipeline — Docker Setup Script
# =============================================================================
# Run this once on the Raspberry Pi before 'docker compose up'.
# Checks system requirements and offers to install missing components
# interactively, then configures the environment for hardware passthrough.
#
# Usage:
#   bash docker/setup.sh          # Interactive: offers to install missing deps
#   bash docker/setup.sh --quiet  # Non-interactive: skips installs, exits on errors
#
# What it does:
#   1. Checks system requirements (Docker, Docker Compose, kernel modules)
#      and offers to install missing components
#   2. Copies .env.sample → .env (if .env doesn't exist yet)
#   3. Detects I2C_GID and GPIO_GID from the host system
#   4. Writes them into .env
#   5. Validates that required hardware devices exist
#   6. Reminds you to set passwords before starting
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
ENV_SAMPLE="$PROJECT_DIR/.env.sample"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

QUIET=false
if [[ "${1:-}" == "--quiet" ]]; then
    QUIET=true
fi

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Helper: Ask yes/no question (returns 0 for yes, 1 for no)
# In --quiet mode, always returns 1 (no)
# ---------------------------------------------------------------------------
ask() {
    if [[ "$QUIET" == true ]]; then
        return 1
    fi
    local prompt="$1"
    local reply
    echo -en "${BOLD}$prompt [y/N]:${NC} "
    read -r reply
    [[ "$reply" =~ ^[Yy]([Ee][Ss])?$ ]]
}

# ---------------------------------------------------------------------------
# Helper: Run a command with sudo, prompting for password if needed
# ---------------------------------------------------------------------------
run_sudo() {
    if [[ $EUID -eq 0 ]]; then
        "$@"
    else
        # Validate sudo access (will prompt for password if needed)
        if ! sudo -v 2>/dev/null; then
            echo ""
            info "This action requires administrator privileges."
            sudo -v
        fi
        sudo "$@"
    fi
}

# ---------------------------------------------------------------------------
# Helper: Track if a relogin is needed
# ---------------------------------------------------------------------------
NEEDS_RELOGIN=false

# ---------------------------------------------------------------------------
# Helper: Fix Raspberry Pi OS Trixie apt signing key issue
# SHA1 signatures were deprecated in Feb 2026, breaking archive.raspberrypi.com
# ---------------------------------------------------------------------------
APT_FIXED=false

fix_raspi_apt() {
    if [[ "$APT_FIXED" == true ]]; then
        return 0
    fi

    # Only relevant on Raspberry Pi OS with the raspi archive
    if [[ ! -f /etc/apt/sources.list.d/raspi.list ]] && ! grep -rq "archive.raspberrypi.com" /etc/apt/sources.list.d/ 2>/dev/null; then
        APT_FIXED=true
        return 0
    fi

    # Test if apt-get update works without issues
    if run_sudo apt-get -qq update 2>/dev/null; then
        APT_FIXED=true
        return 0
    fi

    warn "Raspberry Pi archive has a signing key issue (SHA1 deprecation)."
    info "Attempting to fix by updating the raspberry-pi archive keyring..."

    # Try updating the keyring package first
    if run_sudo apt-get install --allow-unauthenticated -y raspberrypi-archive-keyring 2>/dev/null; then
        ok "Raspberry Pi archive keyring updated"
    else
        # Fallback: temporarily allow the repo to be unauthenticated
        warn "Keyring update failed. Temporarily marking raspi repo as trusted."
        if [[ -f /etc/apt/sources.list.d/raspi.list ]]; then
            run_sudo sed -i 's/^deb /deb [trusted=yes] /' /etc/apt/sources.list.d/raspi.list
        fi
        for f in /etc/apt/sources.list.d/*.sources; do
            if [[ -f "$f" ]] && grep -q "archive.raspberrypi.com" "$f"; then
                run_sudo sed -i '/^Signed-By:/d' "$f"
                if ! grep -q '^Trusted:' "$f"; then
                    run_sudo sed -i '/^URIs:/a Trusted: yes' "$f"
                fi
            fi
        done
        warn "Marked raspi repo as trusted. Re-secure after keyring is fixed upstream."
    fi

    # Retry apt update
    run_sudo apt-get -qq update 2>/dev/null || true
    APT_FIXED=true
}

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Lightning Data Pipeline — Docker Setup"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# ---------------------------------------------------------------------------
# Step 1: System requirements check (with interactive install)
# ---------------------------------------------------------------------------
info "Step 1/5: Checking system requirements..."
echo ""

PREREQ_OK=true

# --- Docker Engine ---
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    ok "Docker Engine installed: v$DOCKER_VERSION"

    # Check if Docker daemon is running
    if docker info &>/dev/null; then
        ok "Docker daemon is running"
    else
        error "Docker daemon is NOT running or current user lacks permissions."
        echo ""

        # Try to start the daemon
        if ask "  Start Docker daemon now? (requires sudo)"; then
            run_sudo systemctl start docker
            run_sudo systemctl enable docker
            ok "Docker daemon started and enabled"

            # Check if user is in docker group
            if ! groups | grep -q docker; then
                warn "Current user is not in the 'docker' group."
                if ask "  Add '$USER' to the docker group? (requires sudo)"; then
                    run_sudo usermod -aG docker "$USER"
                    ok "Added '$USER' to docker group"
                    NEEDS_RELOGIN=true
                    warn "You must log out and back in for group changes to take effect."
                else
                    PREREQ_OK=false
                fi
            fi
        else
            PREREQ_OK=false
        fi
    fi
else
    error "Docker Engine is NOT installed."
    echo ""

    if ask "  Install Docker Engine now? (uses official get.docker.com script, requires sudo)"; then
        echo ""
        fix_raspi_apt
        info "Downloading and running Docker install script..."
        curl -fsSL https://get.docker.com | run_sudo sh
        echo ""

        if command -v docker &>/dev/null; then
            DOCKER_VERSION=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
            ok "Docker Engine installed: v$DOCKER_VERSION"

            # Enable and start
            run_sudo systemctl enable docker
            run_sudo systemctl start docker
            ok "Docker daemon started and enabled"

            # Add user to docker group
            if ! groups | grep -q docker; then
                if ask "  Add '$USER' to the docker group? (avoids needing sudo for docker commands)"; then
                    run_sudo usermod -aG docker "$USER"
                    ok "Added '$USER' to docker group"
                    NEEDS_RELOGIN=true
                fi
            fi
        else
            error "Docker installation failed. Check the output above."
            PREREQ_OK=false
        fi
    else
        error "Docker is required. Install manually:"
        error "  curl -fsSL https://get.docker.com | sh"
        PREREQ_OK=false
    fi
fi

echo ""

# --- Docker Compose (v2 plugin) ---
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || docker compose version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    ok "Docker Compose v2 installed: v$COMPOSE_VERSION"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_VERSION=$(docker-compose --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    warn "Found legacy docker-compose (v1): v$COMPOSE_VERSION"
    warn "  This project requires Docker Compose v2+."
    echo ""

    if ask "  Install Docker Compose v2 plugin now? (requires sudo)"; then
        fix_raspi_apt
        run_sudo apt-get update -qq
        run_sudo apt-get install -y docker-compose-plugin
        if docker compose version &>/dev/null 2>&1; then
            COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
            ok "Docker Compose v2 installed: v$COMPOSE_VERSION"
        else
            error "Docker Compose v2 installation failed."
            PREREQ_OK=false
        fi
    else
        PREREQ_OK=false
    fi
else
    error "Docker Compose is NOT installed."
    echo ""

    if ask "  Install Docker Compose v2 plugin now? (requires sudo)"; then
        fix_raspi_apt
        run_sudo apt-get update -qq
        run_sudo apt-get install -y docker-compose-plugin
        if docker compose version &>/dev/null 2>&1; then
            COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
            ok "Docker Compose v2 installed: v$COMPOSE_VERSION"
        else
            error "Docker Compose installation failed. Try installing Docker first."
            PREREQ_OK=false
        fi
    else
        error "Docker Compose v2 is required. Install manually:"
        error "  sudo apt install docker-compose-plugin"
        PREREQ_OK=false
    fi
fi

echo ""

# --- Git (optional but useful) ---
if command -v git &>/dev/null; then
    GIT_VERSION=$(git --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
    ok "Git installed: v$GIT_VERSION"
else
    warn "Git is not installed (optional, needed only for cloning the repo)."
    if ask "  Install Git now? (requires sudo)"; then
        fix_raspi_apt
        run_sudo apt-get update -qq
        run_sudo apt-get install -y git
        ok "Git installed"
    fi
fi

echo ""

# --- I2C kernel modules ---
I2C_MODULE_LOADED=true

if lsmod 2>/dev/null | grep -q 'i2c_dev'; then
    ok "Kernel module loaded: i2c_dev"
else
    warn "Kernel module 'i2c_dev' is NOT loaded."
    I2C_MODULE_LOADED=false

    if ask "  Load i2c-dev module now and persist across reboots? (requires sudo)"; then
        run_sudo modprobe i2c-dev
        echo 'i2c-dev' | run_sudo tee /etc/modules-load.d/i2c.conf >/dev/null
        if lsmod | grep -q 'i2c_dev'; then
            ok "Kernel module i2c_dev loaded and persisted"
            I2C_MODULE_LOADED=true
        else
            warn "Failed to load i2c_dev. I2C may not be enabled in raspi-config."
        fi
    fi
fi

if lsmod 2>/dev/null | grep -q 'i2c_bcm2835\|i2c_bcm2708'; then
    ok "Kernel module loaded: i2c_bcm2835 (or bcm2708)"
else
    warn "Kernel module 'i2c_bcm2835' is NOT loaded."
    warn "  This is usually loaded automatically when I2C is enabled."

    if command -v raspi-config &>/dev/null; then
        if ask "  Enable I2C interface via raspi-config now? (requires sudo)"; then
            run_sudo raspi-config nonint do_i2c 0
            # Try loading the module
            run_sudo modprobe i2c-bcm2835 2>/dev/null || true
            if lsmod | grep -q 'i2c_bcm2835\|i2c_bcm2708'; then
                ok "I2C enabled and kernel module loaded"
            else
                warn "I2C enabled but module not yet loaded. A reboot may be required."
            fi
        fi
    else
        warn "  raspi-config not found. Enable I2C manually or ensure this is a Pi."
    fi
fi

echo ""

# --- Architecture info ---
ARCH=$(uname -m)
info "Architecture: $ARCH"
if [[ "$ARCH" == "aarch64" || "$ARCH" == "armv7l" || "$ARCH" == "armv6l" ]]; then
    ok "ARM architecture detected (Raspberry Pi compatible)"
else
    warn "Non-ARM architecture detected ($ARCH)."
    warn "  The collector service requires a Raspberry Pi with GPIO/I2C."
    warn "  The API and MariaDB services will work on any architecture."
fi

echo ""

# --- Summary ---
if [[ "$NEEDS_RELOGIN" == true ]]; then
    echo ""
    warn "═══════════════════════════════════════════════════════════════════"
    warn "  You were added to the 'docker' group. You MUST log out and"
    warn "  log back in (or reboot) for this to take effect, then re-run:"
    warn "    bash docker/setup.sh"
    warn "═══════════════════════════════════════════════════════════════════"
    echo ""
    exit 0
fi

if [[ "$PREREQ_OK" == true ]]; then
    ok "All system requirements satisfied."
else
    echo ""
    error "═══════════════════════════════════════════════════════════════════"
    error "  Some system requirements are NOT met. Fix the errors above"
    error "  and re-run this script:  bash docker/setup.sh"
    error "═══════════════════════════════════════════════════════════════════"
    echo ""
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: Create .env from sample if it doesn't exist
# ---------------------------------------------------------------------------
echo ""
info "Step 2/5: Checking .env file..."

if [[ -f "$ENV_FILE" ]]; then
    ok ".env already exists at: $ENV_FILE"
else
    if [[ ! -f "$ENV_SAMPLE" ]]; then
        error ".env.sample not found at: $ENV_SAMPLE"
        error "Are you running this from the project root?"
        exit 1
    fi
    cp "$ENV_SAMPLE" "$ENV_FILE"
    ok "Created .env from .env.sample"
    warn "You MUST edit .env and set secure passwords before starting!"
fi

# ---------------------------------------------------------------------------
# Step 3: Detect I2C group ID
# ---------------------------------------------------------------------------
echo ""
info "Step 3/5: Detecting I2C group ID..."

I2C_GID=""

# Method 1: getent (works on most Linux systems)
if command -v getent &>/dev/null; then
    I2C_GID=$(getent group i2c 2>/dev/null | cut -d: -f3 || true)
fi

# Method 2: stat the device file directly
if [[ -z "$I2C_GID" ]] && [[ -e /dev/i2c-1 ]]; then
    I2C_GID=$(stat -c '%g' /dev/i2c-1 2>/dev/null || true)
fi

# Method 3: parse /etc/group
if [[ -z "$I2C_GID" ]] && [[ -f /etc/group ]]; then
    I2C_GID=$(grep '^i2c:' /etc/group 2>/dev/null | cut -d: -f3 || true)
fi

if [[ -n "$I2C_GID" ]]; then
    ok "I2C group ID detected: $I2C_GID"
else
    warn "Could not detect I2C group ID."
    warn "  Possible causes:"
    warn "    - I2C is not enabled (run: sudo raspi-config → Interface Options → I2C)"
    warn "    - The 'i2c' group doesn't exist (run: sudo groupadd -r i2c)"
    warn "    - /dev/i2c-1 doesn't exist (run: sudo modprobe i2c-dev)"
    warn "  Using fallback GID=998. Edit .env manually if this is wrong."
    I2C_GID=998
fi

# ---------------------------------------------------------------------------
# Step 4: Detect GPIO group ID
# ---------------------------------------------------------------------------
echo ""
info "Step 4/5: Detecting GPIO group ID..."

GPIO_GID=""

# Method 1: getent
if command -v getent &>/dev/null; then
    GPIO_GID=$(getent group gpio 2>/dev/null | cut -d: -f3 || true)
fi

# Method 2: stat /dev/gpiochip0
if [[ -z "$GPIO_GID" ]] && [[ -e /dev/gpiochip0 ]]; then
    GPIO_GID=$(stat -c '%g' /dev/gpiochip0 2>/dev/null || true)
fi

# Method 3: stat /dev/gpiomem
if [[ -z "$GPIO_GID" ]] && [[ -e /dev/gpiomem ]]; then
    GPIO_GID=$(stat -c '%g' /dev/gpiomem 2>/dev/null || true)
fi

# Method 4: parse /etc/group
if [[ -z "$GPIO_GID" ]] && [[ -f /etc/group ]]; then
    GPIO_GID=$(grep '^gpio:' /etc/group 2>/dev/null | cut -d: -f3 || true)
fi

if [[ -n "$GPIO_GID" ]]; then
    ok "GPIO group ID detected: $GPIO_GID"
else
    warn "Could not detect GPIO group ID."
    warn "  Possible causes:"
    warn "    - The 'gpio' group doesn't exist on this system"
    warn "    - /dev/gpiochip0 and /dev/gpiomem don't exist"
    warn "    - This is not a Raspberry Pi (GPIO passthrough won't work)"
    warn "  Using fallback GID=997. Edit .env manually if this is wrong."
    GPIO_GID=997
fi

# ---------------------------------------------------------------------------
# Write GIDs into .env
# ---------------------------------------------------------------------------
echo ""
info "Writing detected GIDs to .env..."

# Replace existing values or append if not present
if grep -q '^I2C_GID=' "$ENV_FILE"; then
    sed -i "s/^I2C_GID=.*/I2C_GID=$I2C_GID/" "$ENV_FILE"
else
    echo "I2C_GID=$I2C_GID" >> "$ENV_FILE"
fi

if grep -q '^GPIO_GID=' "$ENV_FILE"; then
    sed -i "s/^GPIO_GID=.*/GPIO_GID=$GPIO_GID/" "$ENV_FILE"
else
    echo "GPIO_GID=$GPIO_GID" >> "$ENV_FILE"
fi

ok "I2C_GID=$I2C_GID and GPIO_GID=$GPIO_GID written to .env"

# ---------------------------------------------------------------------------
# Step 5: Validate hardware devices
# ---------------------------------------------------------------------------
echo ""
info "Step 5/5: Checking hardware devices..."

ALL_OK=true

if [[ -e /dev/i2c-1 ]]; then
    ok "/dev/i2c-1 exists"
else
    warn "/dev/i2c-1 not found — I2C may not be enabled"
    warn "  Fix: sudo raspi-config → Interface Options → I2C → Enable"
    warn "  Then: sudo modprobe i2c-dev"
    ALL_OK=false
fi

if [[ -e /dev/gpiochip0 ]]; then
    ok "/dev/gpiochip0 exists"
else
    warn "/dev/gpiochip0 not found — GPIO character device missing"
    warn "  This is unusual on Raspberry Pi OS. Check your kernel."
    ALL_OK=false
fi

if [[ -e /dev/gpiomem ]]; then
    ok "/dev/gpiomem exists"
else
    warn "/dev/gpiomem not found (optional, gpiochip0 is preferred)"
    # Not a hard failure
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"

if [[ "$ALL_OK" == true ]]; then
    ok "Setup complete! All checks passed."
else
    warn "Setup complete with warnings. Review the messages above."
fi

echo ""
echo "  Next steps:"
echo "    1. Edit .env and set secure passwords:"
echo "       nano $ENV_FILE"
echo "       (change MARIADB_ROOT_PASSWORD and LIGHTNING_DB_PASSWORD)"
echo ""
echo "    2. Start the stack:"
echo "       docker compose up -d"
echo ""
echo "    3. Check logs:"
echo "       docker compose logs -f"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
