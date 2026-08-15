#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
FLASK_APP_MODULE="${FLASK_APP_MODULE:-app:create_app()}"
RUN_SERVER="${RUN_SERVER:-0}"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-5000}"

log() {
    printf '[deploy] %s\n' "$*"
}

die() {
    printf '[deploy] ERROR: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

generate_secret() {
    "$PYTHON_BIN" - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
}

url_quote() {
    "$PYTHON_BIN" - "$1" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
}

sql_literal() {
    printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"
}

sql_ident() {
    printf '"%s"' "$(printf '%s' "$1" | sed 's/"/""/g')"
}

load_existing_env() {
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    fi
}

configure_variables() {
    FLASK_ENV="${FLASK_ENV:-production}"
    SECRET_KEY="${SECRET_KEY:-}"
    if [[ -z "$SECRET_KEY" || "$SECRET_KEY" == "change-this-secret-before-production" || "$SECRET_KEY" == "replace-with-a-long-random-secret" ]]; then
        SECRET_KEY="$(generate_secret)"
    fi

    ADMIN_USERNAME="${ADMIN_USERNAME:-jonyango}"
    ADMIN_PASSWORD="${ADMIN_PASSWORD:-field.123}"
    DEFAULT_USER_PASSWORD="${DEFAULT_USER_PASSWORD:-field.123}"

    POSTGRES_DB="${POSTGRES_DB:-cleanup_practical}"
    POSTGRES_USER="${POSTGRES_USER:-cleanup_user}"
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
    if [[ -z "$POSTGRES_PASSWORD" || "$POSTGRES_PASSWORD" == "replace-with-a-strong-database-password" ]]; then
        POSTGRES_PASSWORD="$(generate_secret)"
    fi

    POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
    POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5433}"
    POSTGRES_ADMIN_DB="${POSTGRES_ADMIN_DB:-postgres}"
    POSTGRES_ADMIN_USER="${POSTGRES_ADMIN_USER:-}"
    POSTGRES_ADMIN_PASSWORD="${POSTGRES_ADMIN_PASSWORD:-}"
    POSTGRES_ADMIN_URL="${POSTGRES_ADMIN_URL:-}"
    POSTGRES_USE_SUDO="${POSTGRES_USE_SUDO:-auto}"

    DATABASE_URL="postgresql+psycopg2://$(url_quote "$POSTGRES_USER"):$(url_quote "$POSTGRES_PASSWORD")@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
}

write_env_file() {
    umask 077
    cat > "$ENV_FILE" <<EOF
FLASK_ENV=${FLASK_ENV}
SECRET_KEY=${SECRET_KEY}
ADMIN_USERNAME=${ADMIN_USERNAME}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
DEFAULT_USER_PASSWORD=${DEFAULT_USER_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=${POSTGRES_HOST}
POSTGRES_PORT=${POSTGRES_PORT}
POSTGRES_HOST_PORT=${POSTGRES_HOST_PORT}
DATABASE_URL=${DATABASE_URL}
EOF
}

admin_psql() {
    local sql="$1"
    if [[ -n "$POSTGRES_ADMIN_URL" ]]; then
        PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" psql -w "$POSTGRES_ADMIN_URL" -v ON_ERROR_STOP=1 -c "$sql"
    elif [[ "$POSTGRES_USE_SUDO" != "false" ]] && command -v sudo >/dev/null 2>&1 && sudo -n -u postgres true >/dev/null 2>&1; then
        sudo -u postgres psql -w -d "$POSTGRES_ADMIN_DB" -v ON_ERROR_STOP=1 -c "$sql"
    elif [[ -n "$POSTGRES_ADMIN_USER" ]]; then
        PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" psql -w -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_ADMIN_USER" -d "$POSTGRES_ADMIN_DB" -v ON_ERROR_STOP=1 -c "$sql"
    else
        psql -w -d "$POSTGRES_ADMIN_DB" -v ON_ERROR_STOP=1 -c "$sql"
    fi
}

admin_psql_scalar() {
    local sql="$1"
    if [[ -n "$POSTGRES_ADMIN_URL" ]]; then
        PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" psql -w "$POSTGRES_ADMIN_URL" -tAc "$sql"
    elif [[ "$POSTGRES_USE_SUDO" != "false" ]] && command -v sudo >/dev/null 2>&1 && sudo -n -u postgres true >/dev/null 2>&1; then
        sudo -u postgres psql -w -d "$POSTGRES_ADMIN_DB" -tAc "$sql"
    elif [[ -n "$POSTGRES_ADMIN_USER" ]]; then
        PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" psql -w -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_ADMIN_USER" -d "$POSTGRES_ADMIN_DB" -tAc "$sql"
    else
        psql -w -d "$POSTGRES_ADMIN_DB" -tAc "$sql"
    fi
}

create_postgres_role() {
    local role_literal password_literal
    role_literal="$(sql_literal "$POSTGRES_USER")"
    password_literal="$(sql_literal "$POSTGRES_PASSWORD")"

    log "Ensuring PostgreSQL role ${POSTGRES_USER} exists"
    admin_psql "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = ${role_literal}) THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', ${role_literal}, ${password_literal});
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', ${role_literal}, ${password_literal});
    END IF;
END
\$\$;"
}

create_postgres_database() {
    local database_literal database_ident user_ident exists
    database_literal="$(sql_literal "$POSTGRES_DB")"
    database_ident="$(sql_ident "$POSTGRES_DB")"
    user_ident="$(sql_ident "$POSTGRES_USER")"
    exists="$(admin_psql_scalar "SELECT 1 FROM pg_database WHERE datname = ${database_literal};" | tr -d '[:space:]')"

    if [[ "$exists" != "1" ]]; then
        log "Creating PostgreSQL database ${POSTGRES_DB}"
        admin_psql "CREATE DATABASE ${database_ident} OWNER ${user_ident};"
    else
        log "PostgreSQL database ${POSTGRES_DB} already exists"
    fi

    admin_psql "ALTER DATABASE ${database_ident} OWNER TO ${user_ident};"
}

install_python_dependencies() {
    log "Creating/updating Python virtual environment"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "${PROJECT_DIR}/requirements.txt"
}

run_migrations_and_seed_data() {
    log "Running database migrations"
    DATABASE_URL="$DATABASE_URL" "$VENV_DIR/bin/flask" --app "$FLASK_APP_MODULE" db upgrade

    log "Seeding admin user and starter records"
    DATABASE_URL="$DATABASE_URL" "$VENV_DIR/bin/flask" --app "$FLASK_APP_MODULE" seed-data
}

verify_database_connection() {
    log "Verifying app database connection"
    PGPASSWORD="$POSTGRES_PASSWORD" psql -w -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user;"
}

main() {
    cd "$PROJECT_DIR"
    require_command "$PYTHON_BIN"
    require_command psql

    load_existing_env
    configure_variables
    write_env_file
    create_postgres_role
    create_postgres_database
    install_python_dependencies
    run_migrations_and_seed_data
    verify_database_connection

    log "Deployment setup completed"
    log "Environment file: ${ENV_FILE}"
    log "Database URL target: ${POSTGRES_USER}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"

    if [[ "$RUN_SERVER" == "1" ]]; then
        log "Starting Gunicorn on ${APP_HOST}:${APP_PORT}"
        exec "$VENV_DIR/bin/gunicorn" --bind "${APP_HOST}:${APP_PORT}" "$FLASK_APP_MODULE"
    fi
}

main "$@"
