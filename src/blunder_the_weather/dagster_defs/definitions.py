"""Dagster entrypoint: `dagster dev -f src/blunder_the_weather/dagster_defs/definitions.py`."""

from dagster import Definitions
from dotenv import load_dotenv

from blunder_the_weather.config import ENV_PATH
from blunder_the_weather.dagster_defs.assets.bronze import bronze_actuals, bronze_forecasts_historical
from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts
from blunder_the_weather.dagster_defs.jobs import backfill_job
from blunder_the_weather.dagster_defs.resources import build_s3_resource

load_dotenv(ENV_PATH)

defs = Definitions(
    assets=[bronze_actuals, bronze_forecasts_historical, silver_actuals, silver_forecasts],
    jobs=[backfill_job],
    resources={"s3": build_s3_resource()},
)
