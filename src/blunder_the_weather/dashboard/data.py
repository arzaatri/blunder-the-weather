"""Read-only data access for the Streamlit dashboard. Reads gold/ directly from MinIO
via duckdb -- no persisted .duckdb file, no separate database.
"""

from datetime import date

import duckdb
import pandas as pd

from blunder_the_weather.config import load_config
from blunder_the_weather.geo.registry import all_cities, all_grid_points
from blunder_the_weather.lakehouse.duckdb_query import get_connection
from blunder_the_weather.lakehouse.paths import s3_uri
from blunder_the_weather.models.base import ExplanationResult
from blunder_the_weather.models.features import DIMENSION_VALUE_COLUMNS, FEATURE_COLUMNS, build_features
from blunder_the_weather.models.registry import DIMENSIONS, load_model


def latest_scored_date() -> date | None:
    """Most recent issued_date with a gold/predictions partition, or None if
    daily_live_job has never run.

    DISTINCT ... ORDER BY ... LIMIT 1 rather than MAX(dt) -- MAX() over a
    hive-partitioned glob hits a separate DuckDB internal error (statistics
    propagation bug) when there's only one partition present.

    Only "no files match the glob" is treated as "no predictions yet" -- anything
    else (e.g. MinIO unreachable) re-raises, so a connection failure shows up as an
    actual error instead of the misleading "run daily_live_job" message."""
    con = get_connection()
    try:
        row = con.execute(
            f"""
            SELECT DISTINCT dt FROM read_parquet('{s3_uri("gold/predictions/dt=*/part.parquet")}', hive_partitioning=true)
            ORDER BY dt DESC LIMIT 1
            """
        ).fetchone()
    except duckdb.IOException as e:
        if "No files found that match the pattern" in str(e):
            return None
        raise
    return row[0] if row else None


def load_predictions(scored_date: date) -> pd.DataFrame:
    con = get_connection()
    key = s3_uri(f"gold/predictions/dt={scored_date.isoformat()}/part.parquet")
    return con.execute(f"SELECT * FROM read_parquet('{key}')").df()


def load_volatility_scores(scored_date: date) -> pd.DataFrame:
    con = get_connection()
    key = s3_uri(f"gold/volatility_scores/dt={scored_date.isoformat()}/part.parquet")
    return con.execute(f"SELECT * FROM read_parquet('{key}')").df()


def _city_point_ids(city_id: str) -> list[str]:
    return [p.point_id for p in all_grid_points() if p.city_id == city_id]


def city_overview_scores(volatility: pd.DataFrame) -> pd.DataFrame:
    """One row per city (city_id, name, lat, lon, score) -- score is the combined
    volatility score aggregated (per dashboard.city_aggregation) across every grid
    point and lead day, for the dashboard's map overview. This is a coarser rollup
    than city_dimension_table's per-lead-day breakdown -- just enough for "which city
    looks unreliable this week" at a glance."""
    aggregation = load_config().dashboard.city_aggregation
    rows = []
    for city in all_cities():
        points = _city_point_ids(city.city_id)
        city_vol = volatility[volatility["point_id"].isin(points)]
        score = float(city_vol["volatility_score"].agg(aggregation)) if not city_vol.empty else float("nan")
        rows.append({"city_id": city.city_id, "name": city.name, "lat": city.center_lat, "lon": city.center_lon, "score": score})
    return pd.DataFrame(rows)


def city_dimension_table(predictions: pd.DataFrame, volatility: pd.DataFrame, city_id: str) -> pd.DataFrame:
    """One row per lead_days (1-7), one column per dimension (mean/max calibrated
    probability across the city's grid points, per config.dashboard.city_aggregation),
    plus a Combined column from the ensemble volatility score. Also carries valid_date
    for display."""
    aggregation = load_config().dashboard.city_aggregation
    points = _city_point_ids(city_id)

    city_pred = predictions[predictions["point_id"].isin(points)]
    pivot = city_pred.pivot_table(
        index=["valid_date", "lead_days"], columns="dimension", values="calibrated_prob", aggfunc=aggregation
    )
    pivot = pivot.reindex(columns=DIMENSIONS)

    city_vol = volatility[volatility["point_id"].isin(points)]
    combined = city_vol.groupby(["valid_date", "lead_days"])["volatility_score"].agg(aggregation)
    pivot["combined"] = combined

    return pivot.reset_index().sort_values("lead_days")


def explain_city_center(scored_date: date, city_id: str, dimension: str) -> tuple[ExplanationResult, pd.DataFrame]:
    """SHAP explanation for the city's center grid point (the middle of the 3x3 grid,
    point_id "<city_id>_1_1" for the default size=3 layout) across all 7 leads --
    picking one representative point keeps this simple rather than needing to combine
    SHAP values across 9 different feature rows."""
    center_points = [p for p in all_grid_points() if p.city_id == city_id]
    center = next(p for p in center_points if p.point_id.endswith("_1_1"))

    con = get_connection()
    key = s3_uri(f"silver/forecasts_live/dt={scored_date.isoformat()}/part.parquet")
    live_df = con.execute(f"SELECT * FROM read_parquet('{key}') WHERE point_id = ?", [center.point_id]).df()

    value_column = DIMENSION_VALUE_COLUMNS[dimension]
    dim_df = live_df[["point_id", "valid_date", "lead_days"]].copy()
    dim_df["forecast_value"] = live_df[value_column]
    dim_df = build_features(dim_df).sort_values("lead_days")

    registry_df = con.execute(f"SELECT * FROM read_parquet('{s3_uri('gold/model_registry/part.parquet')}')").df()
    version = registry_df.set_index("dimension").loc[dimension, "model_version"]

    model = load_model(dimension, version, _standalone_s3_client())
    explanation = model.explain(dim_df[FEATURE_COLUMNS])
    return explanation, dim_df


class _BotoS3Client:
    """Thin get_client() shim so models.registry.load_model() (written against
    dagster_aws.s3.S3Resource's interface) also works from a plain script/Streamlit
    process. dagster_aws.s3.S3Resource's EnvVar-based credentials only resolve inside
    a live Dagster resource-init context, so it can't be used standalone here --
    same workaround used when verifying Phase 4's models outside of Dagster."""

    def __init__(self, client):
        self._client = client

    def get_client(self):
        return self._client


def _standalone_s3_client() -> _BotoS3Client:
    import boto3

    from blunder_the_weather.config import load_secrets

    cfg = load_config()
    secrets = load_secrets()
    client = boto3.client(
        "s3",
        endpoint_url=cfg.minio.endpoint_url,
        aws_access_key_id=secrets.minio_root_user,
        aws_secret_access_key=secrets.minio_root_password,
    )
    return _BotoS3Client(client)
