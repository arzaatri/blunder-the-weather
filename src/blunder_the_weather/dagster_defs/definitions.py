"""Dagster entrypoint: `dagster dev -f src/blunder_the_weather/dagster_defs/definitions.py`."""

from dagster import Definitions
from dotenv import load_dotenv

from blunder_the_weather.config import ENV_PATH
from blunder_the_weather.dagster_defs.assets.spike import roundtrip_check
from blunder_the_weather.dagster_defs.resources import build_s3_resource

load_dotenv(ENV_PATH)

defs = Definitions(
    assets=[roundtrip_check],
    resources={"s3": build_s3_resource()},
)
