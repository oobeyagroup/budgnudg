#!/usr/bin/env bash
set -euo pipefail

# Simple helper to run E2E Playwright tests locally against a started Django server.
# - Sources .venv if present
# - Sets ENABLE_TEST_API=1 so test-only endpoints are available
# - Starts runserver in background, waits for it, runs pytest against TEST_SERVER_URL
# - Stops server and returns pytest exit code

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Prefer a known test venv path, otherwise source .venv if present
if [ -f "$HOME/venv/budgnudg_env/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$HOME/venv/budgnudg_env/bin/activate"
elif [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate"
fi

export ENABLE_TEST_API=1
HOST=127.0.0.1
PORT=8001
TEST_SERVER_URL="http://$HOST:$PORT"
LOGFILE="/tmp/budgnudg_e2e_server.log"

echo "Starting Django dev server at $TEST_SERVER_URL (logs -> $LOGFILE)"
# Start server in background
python manage.py runserver "$HOST:$PORT" &> "$LOGFILE" &
SERVER_PID=$!

# Wait for server to be ready (timeout ~30s)
for i in {1..30}; do
  if curl -s "$TEST_SERVER_URL/" >/dev/null 2>&1; then
    echo "Server is up"
    break
  fi
  sleep 1
done

if ! curl -s "$TEST_SERVER_URL/" >/dev/null 2>&1; then
  echo "Server failed to start. See log: $LOGFILE" >&2
  tail -n 200 "$LOGFILE" >&2 || true
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  exit 1
fi

# Run the E2E tests against the running server (entire e2e directory)
echo "Running E2E tests against $TEST_SERVER_URL"
TEST_CMD=(pytest -q transactions/tests/e2e)

# Export TEST_SERVER_URL for the test run and execute
TEST_SERVER_URL="$TEST_SERVER_URL" "${TEST_CMD[@]}"
TEST_EXIT=$?

# Stop the server
echo "Stopping Django server (pid $SERVER_PID)"
kill "$SERVER_PID" >/dev/null 2>&1 || true
wait "$SERVER_PID" 2>/dev/null || true

exit "$TEST_EXIT"
