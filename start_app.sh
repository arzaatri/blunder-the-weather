#!/usr/bin/env bash
# Starts the local stack: MinIO (Docker), then the Dagster dev server (webserver +
# daemon bundled). Idempotent -- safe to re-run if some of the stack is already up.
# Streamlit dashboard is added in Phase 6 (src/blunder_the_weather/dashboard/app.py
# doesn't exist yet); once it does, start it here the same way as Dagster below.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

export DAGSTER_HOME="$(pwd)/.dagster_home"
mkdir -p logs .pids

echo "Starting MinIO..."
docker compose up -d

MINIO_URL=$(uv run python -c "from blunder_the_weather.config import load_config; print(load_config().minio.endpoint_url)")
echo "Waiting for MinIO at ${MINIO_URL}..."
until curl -sf "${MINIO_URL}/minio/health/live" > /dev/null 2>&1; do
  sleep 1
done
echo "MinIO is up."

if [ -f .pids/dagster.pid ] && kill -0 "$(cat .pids/dagster.pid)" 2>/dev/null; then
  echo "Dagster already running (PID $(cat .pids/dagster.pid))."
else
  echo "Starting Dagster dev server (DAGSTER_HOME=${DAGSTER_HOME})..."
  : > logs/dagster.log
  # setsid makes this process its own session/process-group leader, so its PID doubles
  # as its process-group ID -- stop_app.sh can then kill -TERM the whole group (dagster
  # dev's actual webserver/daemon/code-server live in child processes; killing only
  # the `uv run` PID leaves them running as orphans, which is what happened before
  # this was added).
  setsid nohup uv run dagster dev -f src/blunder_the_weather/dagster_defs/definitions.py > logs/dagster.log 2>&1 < /dev/null &
  echo $! > .pids/dagster.pid
  echo "Dagster started (PID $(cat .pids/dagster.pid)), logging to logs/dagster.log."
fi

# dagster dev defaults to port 3000 but silently falls back to another free port if
# that's taken, so read the port it actually bound rather than assuming 3000.
DAGSTER_PORT="3000"
for _ in $(seq 1 30); do
  bound_port=$(grep -oE "Serving dagster-webserver on http://[^:]+:[0-9]+" logs/dagster.log | grep -oE "[0-9]+$" | tail -1 || true)
  if [ -n "${bound_port}" ]; then
    DAGSTER_PORT="${bound_port}"
    break
  fi
  sleep 1
done

echo
echo "blunder-the-weather is up."
echo "  Dagster UI: http://localhost:${DAGSTER_PORT}"
echo "  MinIO console: ${MINIO_URL/9100/9101} (see .env for credentials)"
echo "Schedules are defined but stopped by default -- enable them from the Dagster UI when ready."
