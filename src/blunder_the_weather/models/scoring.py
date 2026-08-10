"""Scores a live forecast frame against each dimension's trained model. Decoupled from
Dagster, same pattern as models/training.py, so it can be run directly or wrapped as
an asset (dagster_defs/assets/predictions.py).
"""

import pandas as pd

from blunder_the_weather.models.base import ModelWrapper
from blunder_the_weather.models.features import DIMENSION_VALUE_COLUMNS, FEATURE_COLUMNS, build_features


def score_dimension(model: ModelWrapper, live_df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """live_df: one row per (point_id, valid_date, lead_days) with all five dimensions'
    forecast values as separate columns (the shape of a silver forecast frame)."""
    value_column = DIMENSION_VALUE_COLUMNS[dimension]
    dim_df = live_df[["point_id", "valid_date", "lead_days"]].copy()
    dim_df["forecast_value"] = live_df[value_column]
    dim_df = build_features(dim_df)
    dim_df["calibrated_prob"] = model.predict_proba(dim_df[FEATURE_COLUMNS])
    dim_df["dimension"] = dimension
    return dim_df[["point_id", "valid_date", "lead_days", "dimension", "calibrated_prob"]]


def score_all_dimensions(live_df: pd.DataFrame, models: dict[str, ModelWrapper]) -> pd.DataFrame:
    """Concatenates score_dimension's output across every dimension in `models`."""
    scored = [score_dimension(models[dimension], live_df, dimension) for dimension in models]
    return pd.concat(scored, ignore_index=True)
