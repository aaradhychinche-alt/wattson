#!/usr/bin/env bash
# One-command WATTSON demo for macOS/Linux.
#
#   bash scripts/demo.sh
#
# Starts a Temporal dev server (if one is not already listening), a worker, and
# the API against a fresh demo SQLite database, then runs the end-to-end demo.
# Everything is simulated: no cloud credentials and no paid resources.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TOKEN="${WATTSON_API_TOKEN:-wattson-demo-token}"
TASK_QUEUE="wattson-demo"
DATA_DIR="$ROOT/.data"
LOG_DIR="$DATA_DIR/logs"
API_PORT="${WATTSON_DEMO_API_PORT:-8000}"
mkdir -p "$LOG_DIR" "$DATA_DIR"

export WATTSON_API_TOKEN="$TOKEN"
export WATTSON_TEMPORAL_HOST="localhost:7233"
export WATTSON_TEMPORAL_TASK_QUEUE="$TASK_QUEUE"
export WATTSON_PROVIDER="simulator"
export WATTSON_AI_PROVIDER="none"
export WATTSON_KILL_SWITCH="false"
export WATTSON_DATABASE_URL="sqlite:///$DATA_DIR/demo.db"
export WATTSON_API_URL="http://127.0.0.1:$API_PORT"
rm -f "$DATA_DIR/demo.db" "$DATA_DIR/demo.db-shm" "$DATA_DIR/demo.db-wal"

port_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

wait_port() {
  local port="$1" seconds="$2" i
  for ((i = 0; i < seconds * 2; i++)); do
    if port_open "$port"; then return 0; fi
    sleep 0.5
  done
  return 1
}

TEMPORAL_PID=""
WORKER_PID=""
API_PID=""

cleanup() {
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "$WORKER_PID" ]]; then kill "$WORKER_PID" 2>/dev/null || true; fi
  if [[ -n "$TEMPORAL_PID" ]]; then kill "$TEMPORAL_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

command -v uv >/dev/null || { echo "uv is not installed or not on PATH." >&2; exit 1; }

if ! port_open 7233; then
  command -v temporal >/dev/null || {
    echo "Temporal CLI is not installed. Install it or start a server on localhost:7233." >&2
    exit 1
  }
  echo "Starting Temporal dev server on 127.0.0.1:7233 (headless)..."
  temporal server start-dev --headless --port 7233 \
    --db-filename "$DATA_DIR/temporal-demo.db" \
    >"$LOG_DIR/demo-temporal.out.log" 2>"$LOG_DIR/demo-temporal.err.log" &
  TEMPORAL_PID=$!
  wait_port 7233 45 || { echo "Temporal did not start. See .data/logs/." >&2; exit 1; }
else
  echo "Using the Temporal server already listening on 127.0.0.1:7233."
fi

echo "Starting worker on task queue '$TASK_QUEUE'..."
uv run python -m wattson.worker \
  >"$LOG_DIR/demo-worker.out.log" 2>"$LOG_DIR/demo-worker.err.log" &
WORKER_PID=$!

echo "Starting API on $WATTSON_API_URL ..."
uv run uvicorn wattson.api.app:app --host 127.0.0.1 --port "$API_PORT" \
  >"$LOG_DIR/demo-api.out.log" 2>"$LOG_DIR/demo-api.err.log" &
API_PID=$!

for _ in $(seq 1 120); do
  if curl -fsS "$WATTSON_API_URL/api/health" >/dev/null 2>&1; then break; fi
  sleep 0.5
done
if ! curl -fsS "$WATTSON_API_URL/api/health" >/dev/null 2>&1; then
  echo "API did not become ready. See .data/logs/." >&2
  exit 1
fi

uv run wattson-demo --api-url "$WATTSON_API_URL" --token "$TOKEN"
