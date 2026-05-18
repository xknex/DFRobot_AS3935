#!/usr/bin/env bash
# lightning.sh — manage Lightning Data Pipeline services
#
# Usage:
#   lightning.sh start    [collector|api|db]
#   lightning.sh stop     [collector|api|db]
#   lightning.sh restart  [collector|api|db]
#   lightning.sh status   [collector|api|db]
#   lightning.sh logs     [collector|api|db]  [-f]
#
# Without a service name, the command applies to all services.
# The 'db' target refers to the one-shot schema-init unit (lightning-db-apply).
#
# Examples:
#   lightning.sh start              # start all services
#   lightning.sh restart api        # restart only the REST API
#   lightning.sh status             # show status of all services
#   lightning.sh logs collector -f  # tail collector logs
set -euo pipefail

# -------- Styling --------
if [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  BOLD=$'\e[1m'; RESET=$'\e[0m'
  RED=$'\e[31m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; CYAN=$'\e[36m'
else
  BOLD=""; RESET=""; RED=""; GREEN=""; YELLOW=""; CYAN=""
fi

die()  { printf "%b%s%b\n" "$RED"    "ERROR: $*" "$RESET" >&2; exit 1; }
info() { printf "%b%s%b\n" "$CYAN"   "$*"         "$RESET"; }
ok()   { printf "%b%s%b\n" "$GREEN"  "$*"         "$RESET"; }
warn() { printf "%b%s%b\n" "$YELLOW" "$*"         "$RESET" >&2; }

# -------- Service definitions --------
# Order matters: db-apply runs first, then collector and api depend on it.
ALL_SERVICES=(
  lightning-db-apply
  lightning-collector
  lightning-api
)

# Human-readable aliases
resolve_target() {
  case "${1:-}" in
    collector) echo "lightning-collector" ;;
    api)       echo "lightning-api" ;;
    db)        echo "lightning-db-apply" ;;
    lightning-collector|lightning-api|lightning-db-apply) echo "$1" ;;
    "") echo "" ;;  # empty = all
    *) die "Unknown service target '$1'. Use: collector, api, db, or omit for all." ;;
  esac
}

# -------- Commands --------
cmd_start() {
  local target="$1"
  if [[ -z "$target" ]]; then
    info "Starting all Lightning services..."
    sudo systemctl start lightning-db-apply
    sudo systemctl start lightning-collector lightning-api
    ok "All services started."
  else
    info "Starting $target..."
    sudo systemctl start "$target"
    ok "$target started."
  fi
}

cmd_stop() {
  local target="$1"
  if [[ -z "$target" ]]; then
    info "Stopping all Lightning services..."
    sudo systemctl stop lightning-collector lightning-api || true
    ok "All services stopped."
  else
    info "Stopping $target..."
    sudo systemctl stop "$target" || true
    ok "$target stopped."
  fi
}

cmd_restart() {
  local target="$1"
  if [[ -z "$target" ]]; then
    info "Restarting all Lightning services..."
    sudo systemctl restart lightning-db-apply
    sudo systemctl restart lightning-collector lightning-api
    ok "All services restarted."
  else
    info "Restarting $target..."
    # For db-apply (oneshot), reset-failed first so it can run again
    if [[ "$target" == "lightning-db-apply" ]]; then
      sudo systemctl reset-failed "$target" 2>/dev/null || true
    fi
    sudo systemctl restart "$target"
    ok "$target restarted."
  fi
}

cmd_status() {
  local target="$1"
  local services
  if [[ -z "$target" ]]; then
    services=("${ALL_SERVICES[@]}")
  else
    services=("$target")
  fi

  for svc in "${services[@]}"; do
    printf "\n%b=== %s ===%b\n" "$BOLD" "$svc" "$RESET"
    # --no-pager so it doesn't block; ignore exit code (non-active = non-zero)
    systemctl status "$svc" --no-pager -l 2>&1 || true
  done
}

cmd_logs() {
  local target="$1"; shift || true
  local follow=0
  for arg in "$@"; do
    [[ "$arg" == "-f" || "$arg" == "--follow" ]] && follow=1
  done

  local services
  if [[ -z "$target" ]]; then
    services=("${ALL_SERVICES[@]}")
  else
    services=("$target")
  fi

  if [[ $follow -eq 1 ]]; then
    if [[ ${#services[@]} -eq 1 ]]; then
      exec journalctl -u "${services[0]}" -f
    else
      # journalctl supports multiple -u flags
      local args=()
      for svc in "${services[@]}"; do args+=(-u "$svc"); done
      exec journalctl "${args[@]}" -f
    fi
  else
    local args=()
    for svc in "${services[@]}"; do args+=(-u "$svc"); done
    journalctl "${args[@]}" --no-pager -n 100
  fi
}

# -------- Usage --------
usage() {
  sed -n '1,20p' "$0" | sed 's/^# \{0,1\}//'
}

# -------- Main --------
COMMAND="${1:-}"
shift || true

case "$COMMAND" in
  start|stop|restart|status|logs) ;;
  -h|--help|help) usage; exit 0 ;;
  "") usage; exit 1 ;;
  *) die "Unknown command '$COMMAND'. Use: start, stop, restart, status, logs" ;;
esac

# First remaining arg may be a service target; rest are flags
RAW_TARGET="${1:-}"
shift || true
TARGET="$(resolve_target "$RAW_TARGET")"

case "$COMMAND" in
  start)   cmd_start   "$TARGET" ;;
  stop)    cmd_stop    "$TARGET" ;;
  restart) cmd_restart "$TARGET" ;;
  status)  cmd_status  "$TARGET" ;;
  logs)    cmd_logs    "$TARGET" "$@" ;;
esac
