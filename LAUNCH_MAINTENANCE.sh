#!/usr/bin/env bash
#
# One command to put the PBO Regulatory Authority ICT portal online.
#
#   ./LAUNCH_MAINTENANCE.sh
#
# Brings up the Docker stack (PostgreSQL + the Flask app under gunicorn), then
# publishes it through a Cloudflare Tunnel at https://maintenance.harolditdata.uk.
#
# Safe to run again: every step checks for what it already did. Re-running after
# a `git pull` is the normal way to deploy an update.
#
# Assumes cloudflared is installed and already logged in — that is, running
# `cloudflared tunnel login` once has left a cert.pem in ~/.cloudflared.
#
# Override anything from the environment, e.g.
#   PUBLIC_HOSTNAME=staging.harolditdata.uk ./LAUNCH_MAINTENANCE.sh

set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
TUNNEL_NAME="${TUNNEL_NAME:-pbora-maintenance}"
PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-maintenance.harolditdata.uk}"
APP_PORT="${APP_PORT:-5000}"

# Where `cloudflared tunnel login` put the account certificate, and where the
# systemd service reads its own copy from.
CLOUDFLARED_HOME="${CLOUDFLARED_HOME:-${HOME}/.cloudflared}"
CLOUDFLARED_ETC="${CLOUDFLARED_ETC:-/etc/cloudflared}"

# How long to wait for the app to answer before giving up.
APP_READY_TIMEOUT="${APP_READY_TIMEOUT:-180}"
# Set to 1 to replace an existing DNS record that points somewhere else.
OVERWRITE_DNS="${OVERWRITE_DNS:-0}"
# Set to 1 to bring the stack up without touching the tunnel.
SKIP_TUNNEL="${SKIP_TUNNEL:-0}"

log()  { printf '\033[1;34m[launch]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[launch] WARNING:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[launch] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

trap 'die "failed on line $LINENO. Nothing was rolled back — read the error above, fix it, and run again."' ERR


# --------------------------------------------------------------------------- #
# 1. Preflight
# --------------------------------------------------------------------------- #

preflight() {
    log "Checking the server has what it needs"

    command -v docker >/dev/null 2>&1 || die "docker is not installed."
    docker compose version >/dev/null 2>&1 \
        || die "Docker Compose v2 is missing. The old 'docker-compose' v1 will not work."
    docker info >/dev/null 2>&1 \
        || die "Cannot talk to the Docker daemon. Is it running, and is $USER in the 'docker' group?"

    [[ -f "${PROJECT_DIR}/.env" ]] \
        || die ".env is missing from ${PROJECT_DIR}. It is not in the repository — create it first (see LAUNCH_COMMANDS.md section 2)."

    # A .env that still has a placeholder will start and then fail confusingly.
    if grep -q 'CHANGE_ME' "${PROJECT_DIR}/.env"; then
        die ".env still contains CHANGE_ME. Fill in every value before deploying."
    fi

    local missing=()
    local key
    for key in SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
        grep -qE "^${key}=.+" "${PROJECT_DIR}/.env" || missing+=("$key")
    done
    [[ ${#missing[@]} -eq 0 ]] || die ".env is missing: ${missing[*]}"

    if [[ "$SKIP_TUNNEL" != "1" ]]; then
        command -v cloudflared >/dev/null 2>&1 \
            || die "cloudflared is not installed."
        [[ -f "${CLOUDFLARED_HOME}/cert.pem" ]] \
            || die "No Cloudflare credentials at ${CLOUDFLARED_HOME}/cert.pem. Run: cloudflared tunnel login"
        command -v python3 >/dev/null 2>&1 \
            || die "python3 is needed to read the tunnel list."
        command -v systemctl >/dev/null 2>&1 \
            || die "systemctl not found. This script installs cloudflared as a systemd service."
    fi

    log "Preflight passed"
}


# --------------------------------------------------------------------------- #
# 2. The application stack
# --------------------------------------------------------------------------- #

start_stack() {
    cd "$PROJECT_DIR"

    log "Building the application image"
    docker compose build

    log "Starting PostgreSQL and the application"
    # entrypoint.sh runs `db upgrade` then `seed-data` on every start, so
    # migrations apply themselves here.
    docker compose up -d

    wait_for_app
}

wait_for_app() {
    log "Waiting for the application to answer on port ${APP_PORT}"

    local waited=0
    until curl -fsS -o /dev/null "http://127.0.0.1:${APP_PORT}/login"; do
        if (( waited >= APP_READY_TIMEOUT )); then
            warn "The application did not answer within ${APP_READY_TIMEOUT}s. Recent logs:"
            docker compose logs --tail=40 web >&2 || true
            die "Application did not start."
        fi
        sleep 3
        waited=$(( waited + 3 ))
    done

    log "Application is up after ${waited}s"
}


# --------------------------------------------------------------------------- #
# 3. The Cloudflare tunnel
# --------------------------------------------------------------------------- #

tunnel_id_for() {
    # Prints the UUID of the named tunnel, or nothing when it does not exist.
    # Parsed as JSON rather than scraped: cloudflared does not promise a field
    # order, and the table output does not promise column widths.
    cloudflared tunnel list --output json 2>/dev/null | python3 -c '
import json, sys

wanted = sys.argv[1]
try:
    tunnels = json.load(sys.stdin)
except Exception:
    sys.exit(0)

for tunnel in tunnels or []:
    if tunnel.get("name") == wanted and not tunnel.get("deleted_at"):
        print(tunnel.get("id", ""))
        break
' "$TUNNEL_NAME"
}

ensure_tunnel() {
    log "Looking for a tunnel named '${TUNNEL_NAME}'"

    TUNNEL_ID="$(tunnel_id_for || true)"

    if [[ -z "${TUNNEL_ID:-}" ]]; then
        log "Not found — creating it"
        cloudflared tunnel create "$TUNNEL_NAME"
        TUNNEL_ID="$(tunnel_id_for || true)"
        [[ -n "${TUNNEL_ID:-}" ]] || die "Created the tunnel but could not read its id back."
        log "Created tunnel ${TUNNEL_ID}"
    else
        log "Reusing existing tunnel ${TUNNEL_ID}"
    fi

    CREDENTIALS_FILE="${CLOUDFLARED_HOME}/${TUNNEL_ID}.json"
    [[ -f "$CREDENTIALS_FILE" ]] \
        || die "Tunnel ${TUNNEL_ID} exists in Cloudflare but its credentials file is missing at ${CREDENTIALS_FILE}. Delete the tunnel (cloudflared tunnel delete ${TUNNEL_NAME}) and run again to recreate it."
}

write_tunnel_config() {
    log "Writing the tunnel configuration to ${CLOUDFLARED_ETC}"

    sudo mkdir -p "$CLOUDFLARED_ETC"
    sudo cp "$CREDENTIALS_FILE" "${CLOUDFLARED_ETC}/${TUNNEL_ID}.json"
    sudo chmod 600 "${CLOUDFLARED_ETC}/${TUNNEL_ID}.json"

    sudo tee "${CLOUDFLARED_ETC}/config.yml" >/dev/null <<YAML
# Managed by LAUNCH_MAINTENANCE.sh — edits here are overwritten on the next run.
tunnel: ${TUNNEL_ID}
credentials-file: ${CLOUDFLARED_ETC}/${TUNNEL_ID}.json

# Keep the connection to Cloudflare warm and the logs quiet.
loglevel: info
no-autoupdate: true

ingress:
  - hostname: ${PUBLIC_HOSTNAME}
    service: http://127.0.0.1:${APP_PORT}
    originRequest:
      connectTimeout: 30s
      # The help desk pushes live ticket updates over Socket.IO. Without a long
      # idle timeout Cloudflare closes the WebSocket and the dashboard quietly
      # stops updating.
      tcpKeepAlive: 30s
      keepAliveTimeout: 90s
      httpHostHeader: ${PUBLIC_HOSTNAME}

  # Anything not matched above is not ours to serve.
  - service: http_status:404
YAML

    sudo cloudflared --config "${CLOUDFLARED_ETC}/config.yml" tunnel ingress validate \
        || die "cloudflared rejected the generated config."

    log "Configuration validated"
}

route_dns() {
    log "Pointing ${PUBLIC_HOSTNAME} at the tunnel"

    local args=(tunnel route dns)
    [[ "$OVERWRITE_DNS" == "1" ]] && args+=(--overwrite-dns)
    args+=("$TUNNEL_NAME" "$PUBLIC_HOSTNAME")

    local output
    if output="$(cloudflared "${args[@]}" 2>&1)"; then
        log "DNS record created"
    elif grep -qiE 'already exists|record with that host' <<<"$output"; then
        # Re-running the script lands here every time once DNS is set up.
        log "DNS record already exists — leaving it alone"
    else
        printf '%s\n' "$output" >&2
        die "Could not create the DNS record. If it exists but points elsewhere, re-run with OVERWRITE_DNS=1."
    fi
}

install_tunnel_service() {
    log "Installing cloudflared as a systemd service"

    if systemctl list-unit-files 2>/dev/null | grep -q '^cloudflared\.service'; then
        log "Service already installed — restarting it to pick up the config"
        sudo systemctl restart cloudflared
    else
        sudo cloudflared --config "${CLOUDFLARED_ETC}/config.yml" service install
        sudo systemctl enable cloudflared
        sudo systemctl start cloudflared
    fi

    sleep 5
    if ! systemctl is-active --quiet cloudflared; then
        warn "cloudflared is not running. Recent logs:"
        sudo journalctl -u cloudflared -n 40 --no-pager >&2 || true
        die "The tunnel service failed to start."
    fi

    log "cloudflared is running and enabled at boot"
}


# --------------------------------------------------------------------------- #
# 4. Verify
# --------------------------------------------------------------------------- #

verify_public_url() {
    log "Checking https://${PUBLIC_HOSTNAME} from the outside"

    # DNS propagation and the tunnel's first connection both take a moment.
    local waited=0 code=""
    while (( waited < 90 )); do
        code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 10 \
                 "https://${PUBLIC_HOSTNAME}/login" 2>/dev/null || true)"
        [[ "$code" == "200" ]] && break
        sleep 5
        waited=$(( waited + 5 ))
    done

    if [[ "$code" == "200" ]]; then
        log "https://${PUBLIC_HOSTNAME}/login answered 200"
    else
        warn "https://${PUBLIC_HOSTNAME}/login has not answered 200 yet (last: ${code:-no response})."
        warn "DNS can take a few minutes the first time. Check with:"
        warn "  sudo journalctl -u cloudflared -f"
        return 0
    fi
}

summary() {
    cat <<SUMMARY

$(printf '\033[1;32m')Maintenance portal is live.$(printf '\033[0m')

  URL          https://${PUBLIC_HOSTNAME}
  Tunnel       ${TUNNEL_NAME}  (${TUNNEL_ID:-n/a})
  App          127.0.0.1:${APP_PORT}, not exposed to the internet directly
  Sign in      /login   ·   Create an account  /signup

Everything behind the sign-in is gated. The public pages are /login, /signup,
/confirm/... and the help desk intake at /helpdesk/.

Useful commands:
  docker compose logs -f web          application logs
  sudo journalctl -u cloudflared -f   tunnel logs
  docker compose ps                   what is running
  ./LAUNCH_MAINTENANCE.sh             run again to deploy an update

SUMMARY
}


# --------------------------------------------------------------------------- #

main() {
    cd "$PROJECT_DIR"
    log "Deploying from ${PROJECT_DIR}"

    preflight
    start_stack

    if [[ "$SKIP_TUNNEL" == "1" ]]; then
        log "SKIP_TUNNEL=1 — leaving the tunnel alone"
        log "Application is at http://127.0.0.1:${APP_PORT}"
        exit 0
    fi

    ensure_tunnel
    write_tunnel_config
    route_dns
    install_tunnel_service
    verify_public_url
    summary
}

main "$@"
