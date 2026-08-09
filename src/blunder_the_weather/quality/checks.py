"""Great Expectations validation wired in as Dagster asset checks -- pass/fail shows up
natively in the asset graph rather than as a separate, disconnected report."""

from dagster import AssetCheckResult, asset_check

from blunder_the_weather.dagster_defs.assets.silver import silver_actuals, silver_forecasts
from blunder_the_weather.lakehouse.duckdb_query import get_connection
from blunder_the_weather.lakehouse.paths import s3_uri
from blunder_the_weather.quality.expectations import (
    GOLD_GROUND_TRUTH_LOG_EXPECTATIONS,
    SILVER_ACTUALS_EXPECTATIONS,
    SILVER_FORECASTS_EXPECTATIONS,
)
from blunder_the_weather.quality.validate import validate_dataframe


def _check_result(result, row_count: int) -> AssetCheckResult:
    failed = [r.expectation_config.type for r in result.results if not r.success]
    return AssetCheckResult(passed=result.success, metadata={"rows": row_count, "failed_expectations": failed})


@asset_check(asset=silver_actuals)
def silver_actuals_quality() -> AssetCheckResult:
    df = get_connection().execute(f"SELECT * FROM read_parquet('{s3_uri('silver/actuals/dt=*/part.parquet')}')").df()
    result = validate_dataframe(df, "silver_actuals", SILVER_ACTUALS_EXPECTATIONS)
    return _check_result(result, len(df))


@asset_check(asset=silver_forecasts)
def silver_forecasts_quality() -> AssetCheckResult:
    df = get_connection().execute(f"SELECT * FROM read_parquet('{s3_uri('silver/forecasts/dt=*/part.parquet')}')").df()
    result = validate_dataframe(df, "silver_forecasts", SILVER_FORECASTS_EXPECTATIONS)
    return _check_result(result, len(df))


@asset_check(asset="gold_ground_truth_log")
def gold_ground_truth_log_quality() -> AssetCheckResult:
    df = get_connection().execute(f"SELECT * FROM read_parquet('{s3_uri('gold/ground_truth_log/part.parquet')}')").df()
    result = validate_dataframe(df, "gold_ground_truth_log", GOLD_GROUND_TRUTH_LOG_EXPECTATIONS)
    return _check_result(result, len(df))
