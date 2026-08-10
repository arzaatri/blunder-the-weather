#!/usr/bin/env bash
# Trains all dimension models via Dagster's train_models_job -- a one-off/manual
# script, not part of the start_app.sh/stop_app.sh lifecycle (manually-triggered
# Dagster jobs are run manually, same as the initial backfill). Assumes
# gold_ground_truth_log already exists (from a prior backfill_job + transform_job
# run); brings up MinIO if it isn't already running but doesn't tear it down after --
# that's start_app.sh/stop_app.sh's job.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

export DAGSTER_HOME="$(pwd)/.dagster_home"

echo "Ensuring MinIO is up..."
docker compose up -d

MINIO_URL=$(uv run python -c "from blunder_the_weather.config import load_config; print(load_config().minio.endpoint_url)")
echo "Waiting for MinIO at ${MINIO_URL}..."
until curl -sf "${MINIO_URL}/minio/health/live" > /dev/null 2>&1; do
  sleep 1
done
echo "MinIO is up."

echo "Training all dimension models (train_models_job)..."
uv run dagster job launch -f src/blunder_the_weather/dagster_defs/definitions.py -j train_models_job

echo "Done. Check gold/model_registry/ (or the Dagster UI's Runs page) for results."
