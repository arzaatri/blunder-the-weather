"""Feature engineering for the per-dimension error-probability models.

Pulls from gold/ground_truth_log/ (one row per point x valid_date x lead_days x
dimension) and joins in static geography from the city/grid registry. Deliberately
small for now (no lag/climatology features) since the backfill window is only ~8
days -- widening it later is additive, new columns slot into FEATURE_COLUMNS
without touching model or training code.
"""

import numpy as np
import pandas as pd

from blunder_the_weather.geo.registry import all_cities, all_grid_points
from blunder_the_weather.lakehouse.duckdb_query import get_connection
from blunder_the_weather.lakehouse.paths import s3_uri

_CITY_IDS = sorted(city.city_id for city in all_cities())
_DAYS_PER_YEAR = 365.25

# One-hot city dummies drop the first city to avoid the dummy-variable trap; lat/lon
# capture within-city grid-point variation on top of that.
FEATURE_COLUMNS = [
    "lead_days",
    "lead_days_sq",
    "doy_sin",
    "doy_cos",
    "forecast_value",
    "lat",
    "lon",
    *[f"city_{c}" for c in _CITY_IDS[1:]],
]

# Maps each dimension to its source column in a silver forecast frame (one row per
# point/valid_date/lead_days with all five dimensions as separate columns) -- used to
# build a "forecast_value" column for live scoring, mirroring the per-dimension CTEs in
# dbt/blunder_transform/models/marts/gold_ground_truth_log.sql.
DIMENSION_VALUE_COLUMNS = {
    "temp_max": "temp_max",
    "temp_min": "temp_min",
    "cloud_cover": "cloud_cover_mean",
    "humidity": "humidity_mean",
    "precip_chance": "precip_chance",
}


def _geo_lookup() -> pd.DataFrame:
    points = all_grid_points()
    return pd.DataFrame([{"point_id": p.point_id, "city_id": p.city_id, "lat": p.lat, "lon": p.lon} for p in points])


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds lead_days_sq, doy_sin/cos, lat/lon, and city dummies to a frame that
    already has point_id, valid_date, lead_days, forecast_value columns. Shared by
    training (load_dimension_frame, below) and live scoring (models/scoring.py) so
    the two paths can never silently diverge on how a feature is computed."""
    df = df.merge(_geo_lookup(), on="point_id", how="left")
    if df["city_id"].isna().any():
        raise ValueError("row(s) reference point_id(s) not found in the current geo registry")

    df["valid_date"] = pd.to_datetime(df["valid_date"]).dt.date
    doy = pd.to_datetime(df["valid_date"]).dt.dayofyear
    df["lead_days_sq"] = df["lead_days"] ** 2
    df["doy_sin"] = np.sin(2 * np.pi * doy / _DAYS_PER_YEAR)
    df["doy_cos"] = np.cos(2 * np.pi * doy / _DAYS_PER_YEAR)
    for c in _CITY_IDS[1:]:
        df[f"city_{c}"] = (df["city_id"] == c).astype(float)
    return df


def load_dimension_frame(dimension: str) -> pd.DataFrame:
    """One row per (point, valid_date, lead_days) for a single dimension, with
    features built and target (is_large_error) attached. Keeps valid_date so callers
    can do a time-based train/holdout split."""
    con = get_connection()
    gold = con.execute(
        f"""
        select point_id, valid_date, lead_days, forecast_value, is_large_error
        from read_parquet('{s3_uri("gold/ground_truth_log/part.parquet")}')
        where dimension = ?
        """,
        [dimension],
    ).df()

    df = build_features(gold)
    df["target"] = df["is_large_error"].astype(int)
    return df
