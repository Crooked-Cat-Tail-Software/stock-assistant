#!/usr/bin/env bash
# Wait until a deployed service reports the expected git commit.
#
#   wait-for-commit.sh <url> <expected-sha> [timeout-seconds]
#
# <url> returns either JSON with a "commit" field (backend /api/health) or the
# bare commit as plain text (frontend /version). Free Render services can take
# several minutes to build and start, so the default timeout is 15 minutes.
set -euo pipefail

url=$1
expected=$2
timeout=${3:-900}
deadline=$((SECONDS + timeout))

while (( SECONDS < deadline )); do
  body=$(curl -fsS --max-time 30 "$url" 2>/dev/null || true)
  actual=$(jq -r '.commit // empty' <<<"$body" 2>/dev/null || true)
  [[ -z $actual ]] && actual=$(tr -d '[:space:]' <<<"$body")
  if [[ $actual == "$expected" ]]; then
    echo "✓ $url is running $expected"
    exit 0
  fi
  echo "… $url reports '${actual:-no response}', waiting for $expected"
  sleep 15
done

echo "::error::Timed out after ${timeout}s waiting for $url to run $expected"
exit 1
