#!/bin/sh
# Start the single-service container: migrations, then the API on loopback,
# then nginx. If either process exits, stop the container so the platform
# restarts it (rather than serving a site with half of it dead).
set -eu

# Same resolver discovery as the nginx image's 15-local-resolvers.envsh.
NGINX_LOCAL_RESOLVERS=$(awk 'BEGIN{ORS=" "} $1=="nameserver" {if ($2 ~ ":") {print "["$2"]"} else {print $2}}' /etc/resolv.conf)
export NGINX_LOCAL_RESOLVERS="${NGINX_LOCAL_RESOLVERS% }"

# Substitute only our variables; nginx's own $variables must stay as they are.
envsubst '${BACKEND_URL} ${INTERNAL_API_TOKEN} ${TRUSTED_PROXY_CIDR} ${REAL_IP_HEADER} ${RENDER_GIT_COMMIT} ${NGINX_LOCAL_RESOLVERS}' \
    < /etc/stock-assistant/site.conf.template > /tmp/nginx-site.conf
nginx -t -c /etc/stock-assistant/nginx.conf -q

alembic upgrade head

# Only nginx (127.0.0.1) may set the forwarded client IP.
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips 127.0.0.1 &
api_pid=$!

# Start nginx only once the API answers. The platform holds a waking visitor's
# request until the port opens; opening it early would hand that visitor a 502
# while Python is still importing (the very symptom of issue #24).
# Stop at once if the API process dies (e.g. a missing key), so the real error
# above is the last thing in the log (issue #27). The free plan's CPU is tiny,
# so allow a slow cold start.
API_PID="$api_pid" python - <<'PY'
import os, sys, time, urllib.request
pid = int(os.environ["API_PID"])
deadline = time.monotonic() + 300
while time.monotonic() < deadline:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        sys.exit("start-stock-assistant: the API exited during startup (see the error above)")
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
sys.exit("start-stock-assistant: API did not become ready within 300 s")
PY

nginx -c /etc/stock-assistant/nginx.conf -g 'daemon off;' &
nginx_pid=$!

trap 'kill -TERM "$api_pid" "$nginx_pid" 2>/dev/null' INT TERM

# Exit when either process exits (POSIX sh has no `wait -n`).
while kill -0 "$api_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 2
done
echo "start-stock-assistant: a process exited; stopping container" >&2
kill -TERM "$api_pid" "$nginx_pid" 2>/dev/null || true
wait
exit 1
