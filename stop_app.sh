#!/usr/bin/env bash
# Tears down the local stack: stops Dagster, then MinIO. MinIO's data volume is left
# intact (no `docker compose down -v`), so restarting with start_app.sh picks up
# right where this left off.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f .pids/dagster.pid ]; then
  pid="$(cat .pids/dagster.pid)"
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Stopping Dagster (PID ${pid})..."
    # Negative PID = signal the whole process group (start_app.sh launches Dagster via
    # setsid so its PID is also its process-group ID) -- dagster dev's real work
    # happens in child processes (webserver, daemon, code server), and killing just
    # the top PID leaves those running as orphans.
    kill -TERM "-${pid}" 2>/dev/null || kill "${pid}"
    for _ in $(seq 1 10); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 1
    done
    kill -9 "-${pid}" 2>/dev/null || true
  fi
  rm -f .pids/dagster.pid
fi

echo "Stopping MinIO..."
docker compose down

echo "blunder-the-weather is stopped. MinIO data persists (use 'docker compose down -v' to wipe it)."
