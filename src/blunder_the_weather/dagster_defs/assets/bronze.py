"""Bronze-layer assets: land near-raw Open-Meteo API responses to MinIO, partitioned by
date. Deliberately tied to the concrete Open-Meteo provider classes (not the swappable
Protocol/factory) -- what "raw" looks like is inherently source-specific; that's exactly
what the bronze layer is for. Silver assets parse this into the source-agnostic
canonical schema, and can be rebuilt from bronze without re-hitting the API.
"""

from datetime import date

from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_aws.s3 import S3Resource

from blunder_the_weather.dagster_defs.partitions import BACKFILL_PARTITIONS
from blunder_the_weather.geo.registry import all_grid_points
from blunder_the_weather.lakehouse.io import put_json
from blunder_the_weather.lakehouse.paths import BRONZE, s3_uri
from blunder_the_weather.providers.base import DEFAULT_LEAD_DAYS
from blunder_the_weather.providers.open_meteo.actuals import OpenMeteoActualsProvider
from blunder_the_weather.providers.open_meteo.historical_forecast import OpenMeteoHistoricalForecastProvider


@asset(partitions_def=BACKFILL_PARTITIONS, group_name="bronze")
def bronze_actuals(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    partition_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = OpenMeteoActualsProvider().fetch_raw(points, partition_date, partition_date)

    key = f"{BRONZE}/actuals/dt={partition_date.isoformat()}/data.json"
    put_json(s3, key, raw_entries)
    context.log.info(f"Landed {len(raw_entries)} point-entries to {s3_uri(key)}")
    return MaterializeResult(metadata={"points": len(raw_entries)})


@asset(partitions_def=BACKFILL_PARTITIONS, group_name="bronze")
def bronze_forecasts_historical(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    partition_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = OpenMeteoHistoricalForecastProvider().fetch_raw(
        points, partition_date, partition_date, DEFAULT_LEAD_DAYS
    )

    key = f"{BRONZE}/forecasts_historical/dt={partition_date.isoformat()}/data.json"
    put_json(s3, key, raw_entries)
    context.log.info(f"Landed {len(raw_entries)} point-entries to {s3_uri(key)}")
    return MaterializeResult(metadata={"points": len(raw_entries)})
