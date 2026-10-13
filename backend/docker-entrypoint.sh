#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
    for variable in POSTGRES_HOST POSTGRES_PORT POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
        eval "value=\${$variable:-}"
        if [ -z "$value" ]; then
            echo "ERROR: $variable is required when DATABASE_URL is not set." >&2
            exit 1
        fi
    done

    DATABASE_URL="$(python -c 'import os; from urllib.parse import quote_plus as q; print("postgresql+psycopg://{}:{}@{}:{}/{}".format(q(os.environ["POSTGRES_USER"]), q(os.environ["POSTGRES_PASSWORD"]), os.environ["POSTGRES_HOST"], os.environ["POSTGRES_PORT"], q(os.environ["POSTGRES_DB"])))')"
    export DATABASE_URL
fi

if [ -z "${MODEL_CONFIG_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: MODEL_CONFIG_ENCRYPTION_KEY is required. Generate a Fernet key and set it in .env." >&2
    exit 1
fi

if [ -n "${INITIAL_ADMIN_EMAIL:-}" ] && [ -z "${INITIAL_ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: INITIAL_ADMIN_PASSWORD is required when INITIAL_ADMIN_EMAIL is set." >&2
    exit 1
fi

if [ -z "${INITIAL_ADMIN_EMAIL:-}" ] && [ -n "${INITIAL_ADMIN_PASSWORD:-}" ]; then
    echo "ERROR: INITIAL_ADMIN_EMAIL is required when INITIAL_ADMIN_PASSWORD is set." >&2
    exit 1
fi

python -c 'from app.core.security import SecretCipher; SecretCipher().encrypt("startup-check")'

echo "Applying database migrations..."
alembic upgrade head

echo "Starting FastAPI..."
exec "$@"
