#!/bin/sh
# Apply database migrations, then start the API.
# Running migrations at startup is fine for a single instance. With several
# instances they should run once as a separate release step instead.
set -e

alembic upgrade head

# --proxy-headers lets the rate limiter see the real client IP that nginx
# forwards. FORWARDED_ALLOW_IPS says which proxies to trust. The default "*" is
# safe only because the backend is never exposed directly (see docker-compose.yml).
exec uvicorn app.main:create_app --factory \
    --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"
