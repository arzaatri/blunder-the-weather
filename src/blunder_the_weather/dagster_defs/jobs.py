"""Dagster jobs. backfill_job materializes bronze + silver for the whole configured
backfill window across all grid points; Dagster's partitioned-backfill UI drives it
one (or many) partitions at a time."""

from dagster import AssetSelection, define_asset_job

from blunder_the_weather.dagster_defs.assets.bronze import bronze_actuals, bronze_forecasts_historical
from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts

backfill_job = define_asset_job(
    name="backfill_job",
    selection=AssetSelection.assets(bronze_actuals, bronze_forecasts_historical, silver_actuals, silver_forecasts),
)
