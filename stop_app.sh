#!/usr/bin/env bash
# Tears down the local stack: stops Streamlit and Dagster, then MinIO. MinIO's data
# volume is left intact (no `docker compose down -v`), so restarting with
# start_app.sh picks up right where this left off.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Negative PID = signal the whole process group (start_app.sh launches both via setsid
# so each PID doubles as its process-group ID) -- both dagster dev and streamlit run
# do their real work in child processes, and killing just the top PID leaves those
# running as orphans (confirmed the hard way while building this).
stop_pidfile() {
  local name="$1" pidfile="$2"
  [ -f "${pidfile}" ] || return 0
  local pid
  pid="$(cat "${pidfile}")"
  if kill -0 "${pid}" 2>/dev/null; then
    echo "Stopping ${name} (PID ${pid})..."
    kill -TERM "-${pid}" 2>/dev/null || kill "${pid}"
    for _ in $(seq 1 10); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 1
    done
    kill -9 "-${pid}" 2>/dev/null || true
  fi
  rm -f "${pidfile}"
}

stop_pidfile "Streamlit" .pids/streamlit.pid
stop_pidfile "Dagster" .pids/dagster.pid

echo "Stopping MinIO..."
docker compose down

echo "blunder-the-weather is stopped. MinIO data persists (use 'docker compose down -v' to wipe it)."
