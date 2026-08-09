"""Dagster jobs. backfill_job materializes bronze + silver for the whole configured
backfill window across all grid points; Dagster's partitioned-backfill UI drives it
one (or many) partitions at a time."""

from dagster import AssetSelection, define_asset_job

from blunder_the_weather.dagster_defs.assets.bronze import bronze_actuals, bronze_forecasts_historical
from blunder_the_weather.dagster_defs.assets.gold import blunder_dbt_assets
from blunder_the_weather.dagster_defs.assets.models import DIMENSION_MODEL_ASSETS, model_registry
from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts
from blunder_the_weather.quality.checks import gold_ground_truth_log_quality, silver_actuals_quality, silver_forecasts_quality

backfill_job = define_asset_job(
    name="backfill_job",
    selection=AssetSelection.assets(bronze_actuals, bronze_forecasts_historical, silver_actuals, silver_forecasts),
)

transform_job = define_asset_job(
    name="transform_job",
    selection=AssetSelection.assets(blunder_dbt_assets),
)

# Standalone check execution: these checks are unpartitioned even though silver_actuals/
# silver_forecasts are partitioned, so they run against already-materialized data rather
# than as part of a partition's own materialization run (see Phase 2+ notes).
quality_checks_job = define_asset_job(
    name="quality_checks_job",
    selection=AssetSelection.checks(silver_actuals_quality, silver_forecasts_quality, gold_ground_truth_log_quality),
)

# Manual for now -- Phase 5 adds a scheduled retrain_job once there's a live pipeline
# feeding gold continuously.
train_models_job = define_asset_job(
    name="train_models_job",
    selection=AssetSelection.assets(*DIMENSION_MODEL_ASSETS, model_registry),
)
