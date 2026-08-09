"""Silver-layer assets: parse bronze JSON into the canonical schemas, typed and ready
for gold-layer labeling/features, as Parquet. Reads from bronze (not the live API), so
a mapping bug can be fixed and silver rebuilt without spending API calls."""

from datetime import date

import pandas as pd
from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_aws.s3 import S3Resource

from blunder_the_weather.dagster_defs.assets.bronze import bronze_actuals, bronze_forecasts_historical
from blunder_the_weather.dagster_defs.partitions import BACKFILL_PARTITIONS
from blunder_the_weather.geo.registry import all_grid_points
from blunder_the_weather.lakehouse.io import get_json, put_parquet
from blunder_the_weather.lakehouse.paths import BRONZE, SILVER, s3_uri
from blunder_the_weather.providers.base import DEFAULT_LEAD_DAYS
from blunder_the_weather.providers.open_meteo.mappings import (
    assert_point_alignment,
    parse_actuals,
    parse_historical_forecast_range,
)


@asset(partitions_def=BACKFILL_PARTITIONS, deps=[bronze_actuals], group_name="silver")
def silver_actuals(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    partition_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = get_json(s3, f"{BRONZE}/actuals/dt={partition_date.isoformat()}/data.json")
    assert_point_alignment(raw_entries, points)

    observations = [obs for point, entry in zip(points, raw_entries) for obs in parse_actuals(entry["daily"], point)]
    df = pd.DataFrame([o.model_dump() for o in observations])

    key = f"{SILVER}/actuals/dt={partition_date.isoformat()}/part.parquet"
    put_parquet(s3, key, df)
    context.log.info(f"Wrote {len(df)} rows to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(df)})


@asset(partitions_def=BACKFILL_PARTITIONS, deps=[bronze_forecasts_historical], group_name="silver")
def silver_forecasts(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    partition_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = get_json(s3, f"{BRONZE}/forecasts_historical/dt={partition_date.isoformat()}/data.json")
    assert_point_alignment(raw_entries, points)

    records = [
        record
        for point, entry in zip(points, raw_entries)
        for record in parse_historical_forecast_range(
            entry["hourly"], point, partition_date, partition_date, DEFAULT_LEAD_DAYS
        )
    ]
    df = pd.DataFrame([r.model_dump() for r in records])

    key = f"{SILVER}/forecasts/dt={partition_date.isoformat()}/part.parquet"
    put_parquet(s3, key, df)
    context.log.info(f"Wrote {len(df)} rows to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(df)})
