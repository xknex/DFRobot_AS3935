#!/usr/bin/env bash
# =============================================================================
# Lightning Data Pipeline — Docker Setup Script
# =============================================================================
# Run this once on the Raspberry Pi before 'docker compose up'.
# It creates .env from .env.sample (if not present) and auto-detects the
# host's I2C and GPIO group IDs needed for hardware device passthrough.
#
# Usage:
#   bash docker/setup.sh          # Interactive: prompts for missing passwords
#   bash docker/setup.sh --quiet  # Non-interactive: uses defaults, no prompts
#
# What it does:
#   1. Copies .env.sample → .env (if .env doesn't exist yet)
#   2. Detects I2C_GID and GPIO_GID from the host system
#   3. Writes them into .env
#   4. Validates that required hardware devices exist
#   5. Reminds you to set passwords before starting
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
NC='\033[0m' # No Color

QUIET=false
if [[ "${1:-}" == "--quiet" ]]; then
    QUIET=true
fi

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Lightning Data Pipeline — Docker Setup"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Create .env from sample if it doesn't exist
# ---------------------------------------------------------------------------
info "Step 1/4: Checking .env file..."

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
# Step 2: Detect I2C group ID
# ---------------------------------------------------------------------------
info "Step 2/4: Detecting I2C group ID..."

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
# Step 3: Detect GPIO group ID
# ---------------------------------------------------------------------------
info "Step 3/4: Detecting GPIO group ID..."

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
# Step 4: Validate hardware devices
# ---------------------------------------------------------------------------
info "Step 4/4: Checking hardware devices..."

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
    ok "Setup complete! Hardware devices detected."
else
    warn "Setup complete with warnings. Review the messages above."
fi

echo ""
echo "  Next steps:"
echo "    1. Edit .env and set secure passwords:"
echo "       - MARIADB_ROOT_PASSWORD"
echo "       - LIGHTNING_DB_PASSWORD"
echo ""
echo "    2. Start the stack:"
echo "       docker compose up -d"
echo ""
echo "    3. Check logs:"
echo "       docker compose logs -f"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
