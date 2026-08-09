"""Dagster entrypoint: `dagster dev -f src/blunder_the_weather/dagster_defs/definitions.py`."""

from dagster import Definitions
from dagster_dbt import DbtCliResource
from dotenv import load_dotenv

from blunder_the_weather.config import ENV_PATH
from blunder_the_weather.dagster_defs.assets.bronze import bronze_actuals, bronze_forecasts_historical
from blunder_the_weather.dagster_defs.assets.gold import blunder_dbt_assets
from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts
from blunder_the_weather.dagster_defs.dbt_project import dbt_project
from blunder_the_weather.dagster_defs.jobs import backfill_job, quality_checks_job, transform_job
from blunder_the_weather.dagster_defs.resources import build_s3_resource
from blunder_the_weather.quality.checks import (
    gold_ground_truth_log_quality,
    silver_actuals_quality,
    silver_forecasts_quality,
)

load_dotenv(ENV_PATH)

defs = Definitions(
    assets=[bronze_actuals, bronze_forecasts_historical, silver_actuals, silver_forecasts, blunder_dbt_assets],
    asset_checks=[silver_actuals_quality, silver_forecasts_quality, gold_ground_truth_log_quality],
    jobs=[backfill_job, transform_job, quality_checks_job],
    resources={
        "s3": build_s3_resource(),
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
)
