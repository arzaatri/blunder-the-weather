"""Live scoring: pulls today's operational forecast (Forecast API, via
LiveForecastProvider -- not the Previous Runs API used for training), scores it
against each dimension's active trained model, and combines the five probabilities
into one ensemble volatility score per (point, valid_date, lead_days). Separate from
backfill_job's historical assets: live forecasts land under their own bronze/silver
prefixes and never feed gold_ground_truth_log, since Risk 2 in the plan flags that
live (Forecast API) and backfill (Previous Runs API) may not be perfectly
distributionally identical -- keeping them apart avoids silently mixing that into
training data without a deliberate review.
"""

from datetime import date, datetime, timezone

import pandas as pd
from dagster import AssetExecutionContext, MaterializeResult, asset
from dagster_aws.s3 import S3Resource

from blunder_the_weather.dagster_defs.assets.models import model_registry
from blunder_the_weather.dagster_defs.partitions import LIVE_PARTITIONS
from blunder_the_weather.geo.registry import all_grid_points
from blunder_the_weather.lakehouse.duckdb_query import get_connection
from blunder_the_weather.lakehouse.io import get_json, put_json, put_parquet
from blunder_the_weather.lakehouse.paths import BRONZE, GOLD, SILVER, s3_uri
from blunder_the_weather.models.ensemble import build_ensemble
from blunder_the_weather.models.registry import DIMENSIONS, load_model
from blunder_the_weather.models.scoring import score_all_dimensions
from blunder_the_weather.providers.open_meteo.live_forecast import OpenMeteoLiveForecastProvider
from blunder_the_weather.providers.open_meteo.mappings import assert_point_alignment, parse_live_forecast


@asset(partitions_def=LIVE_PARTITIONS, group_name="bronze")
def bronze_forecasts_live(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    issued_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = OpenMeteoLiveForecastProvider().fetch_raw(points)

    key = f"{BRONZE}/forecasts_live/dt={issued_date.isoformat()}/data.json"
    put_json(s3, key, raw_entries)
    context.log.info(f"Landed {len(raw_entries)} point-entries to {s3_uri(key)}")
    return MaterializeResult(metadata={"points": len(raw_entries)})


@asset(partitions_def=LIVE_PARTITIONS, deps=[bronze_forecasts_live], group_name="silver")
def silver_forecasts_live(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    issued_date = date.fromisoformat(context.partition_key)
    points = all_grid_points()
    raw_entries = get_json(s3, f"{BRONZE}/forecasts_live/dt={issued_date.isoformat()}/data.json")
    assert_point_alignment(raw_entries, points)

    records = [
        record
        for point, entry in zip(points, raw_entries)
        for record in parse_live_forecast(entry["daily"], point, issued_date)
    ]
    df = pd.DataFrame([r.model_dump() for r in records])

    key = f"{SILVER}/forecasts_live/dt={issued_date.isoformat()}/part.parquet"
    put_parquet(s3, key, df)
    context.log.info(f"Wrote {len(df)} rows to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(df)})


@asset(partitions_def=LIVE_PARTITIONS, deps=[silver_forecasts_live, model_registry], group_name="gold")
def gold_predictions(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    issued_date = date.fromisoformat(context.partition_key)
    con = get_connection()

    live_df = con.execute(
        f"SELECT * FROM read_parquet('{s3_uri(f'{SILVER}/forecasts_live/dt={issued_date.isoformat()}/part.parquet')}')"
    ).df()

    registry_df = con.execute(f"SELECT * FROM read_parquet('{s3_uri(f'{GOLD}/model_registry/part.parquet')}')").df()
    models = {
        row["dimension"]: load_model(row["dimension"], row["model_version"], s3) for _, row in registry_df.iterrows()
    }
    missing = set(DIMENSIONS) - set(models)
    if missing:
        raise ValueError(f"model_registry is missing entries for dimensions: {sorted(missing)}")

    scored = score_all_dimensions(live_df, models)
    scored["scored_date"] = issued_date
    scored["model_version"] = scored["dimension"].map(registry_df.set_index("dimension")["model_version"])
    scored["created_at"] = datetime.now(timezone.utc)

    key = f"{GOLD}/predictions/dt={issued_date.isoformat()}/part.parquet"
    put_parquet(s3, key, scored)
    context.log.info(f"Wrote {len(scored)} prediction rows to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(scored)})


@asset(partitions_def=LIVE_PARTITIONS, deps=[gold_predictions], group_name="gold")
def gold_volatility_scores(context: AssetExecutionContext, s3: S3Resource) -> MaterializeResult:
    issued_date = date.fromisoformat(context.partition_key)
    con = get_connection()

    predictions = con.execute(
        f"SELECT * FROM read_parquet('{s3_uri(f'{GOLD}/predictions/dt={issued_date.isoformat()}/part.parquet')}')"
    ).df()

    ensemble = build_ensemble()
    rows = []
    grouped = predictions.groupby(["point_id", "valid_date", "lead_days"])
    for (point_id, valid_date, lead_days), group in grouped:
        dimension_probs = dict(zip(group["dimension"], group["calibrated_prob"]))
        rows.append(
            {
                "point_id": point_id,
                "scored_date": issued_date,
                "valid_date": valid_date,
                "lead_days": lead_days,
                "volatility_score": ensemble.combine(dimension_probs),
                "ensemble_method": type(ensemble).__name__,
                "created_at": datetime.now(timezone.utc),
            }
        )
    df = pd.DataFrame(rows)

    key = f"{GOLD}/volatility_scores/dt={issued_date.isoformat()}/part.parquet"
    put_parquet(s3, key, df)
    context.log.info(f"Wrote {len(df)} volatility score rows to {s3_uri(key)}")
    return MaterializeResult(metadata={"rows": len(df)})
