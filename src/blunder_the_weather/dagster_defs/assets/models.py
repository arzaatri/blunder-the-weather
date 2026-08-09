"""Model-training assets: one per dimension (depends on the dbt gold model), plus a
fan-in asset that assembles gold/model_registry/ from what each produced. Run
manually via train_models_job for now -- not wired to any schedule (Phase 5).
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dagster import AssetExecutionContext, AssetsDefinition, MaterializeResult, asset
from dagster_aws.s3 import S3Resource

from blunder_the_weather.lakehouse.io import get_json, put_json, put_parquet, upload_dir_to_s3
from blunder_the_weather.lakehouse.paths import s3_uri
from blunder_the_weather.models.registry import DIMENSIONS, model_prefix
from blunder_the_weather.models.training import train_and_evaluate


def _run_version(context: AssetExecutionContext) -> str:
    """Dagster's multiprocess executor runs each step in its own subprocess, re-
    importing this module -- so a module-level timestamp constant would differ per
    step. context.run_id is set once for the whole run and shared across every step
    within it, which is what the fan-in model_registry asset below needs to find
    what each dimension asset just wrote."""
    return f"{datetime.now(timezone.utc):%Y%m%d}_{context.run_id[:8]}"


def _train_dimension_asset(dimension: str) -> AssetsDefinition:
    @asset(name=f"model_{dimension}", deps=["gold_ground_truth_log"], group_name="models")
    def _asset(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
        version = _run_version(context)
        result = train_and_evaluate(dimension)

        with tempfile.TemporaryDirectory() as tmp:
            result.model.save(Path(tmp))
            upload_dir_to_s3(s3, Path(tmp), model_prefix(dimension, version))

        registry_entry = {
            "dimension": dimension,
            "model_version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_window_start": result.train_window[0].isoformat(),
            "training_window_end": result.train_window[1].isoformat(),
            "n_train_rows": result.n_train_rows,
            "n_holdout_rows": result.n_holdout_rows,
            "metrics_json": json.dumps(result.metrics),
            "calibration_method": "sigmoid_prefit",
            "is_active": True,
        }
        put_json(s3, f"{model_prefix(dimension, version)}/registry_entry.json", registry_entry)
        context.log.info(f"Trained {dimension} ({version}): {result.metrics}")
        return MaterializeResult(metadata={**result.metrics, "n_train_rows": result.n_train_rows})

    return _asset


model_temp_max = _train_dimension_asset("temp_max")
model_cloud_cover = _train_dimension_asset("cloud_cover")
model_humidity = _train_dimension_asset("humidity")
model_precip_chance = _train_dimension_asset("precip_chance")

DIMENSION_MODEL_ASSETS = [model_temp_max, model_cloud_cover, model_humidity, model_precip_chance]


@asset(deps=DIMENSION_MODEL_ASSETS, group_name="models")
def model_registry(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    version = _run_version(context)
    rows = [get_json(s3, f"{model_prefix(dimension, version)}/registry_entry.json") for dimension in DIMENSIONS]
    df = pd.DataFrame(rows)

    key = "gold/model_registry/part.parquet"
    put_parquet(s3, key, df)
    context.log.info(f"Wrote model registry ({len(df)} rows) to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(df)})
