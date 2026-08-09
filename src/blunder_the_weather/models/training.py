"""Core train/evaluate logic for one dimension's error-probability model, decoupled
from Dagster so it can be run directly or wrapped as an asset
(dagster_defs/assets/models.py).
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from blunder_the_weather.config import load_config
from blunder_the_weather.models.base import ModelWrapper
from blunder_the_weather.models.features import FEATURE_COLUMNS, load_dimension_frame
from blunder_the_weather.models.registry import build_model


@dataclass
class TrainResult:
    dimension: str
    model: ModelWrapper
    feature_names: list[str]
    metrics: dict[str, float]
    train_window: tuple[date, date]
    n_train_rows: int
    n_holdout_rows: int


def _lead_shape_mae(holdout: pd.DataFrame, pred: np.ndarray) -> float:
    """Mean absolute gap, per lead_days bucket, between the model's average
    predicted probability and the empirical positive rate -- a cheap check that a
    linear model isn't visibly underfitting how error probability grows with lead
    time (see plan risk notes)."""
    shape = holdout.assign(pred=pred).groupby("lead_days").agg(pred_mean=("pred", "mean"), empirical=("target", "mean"))
    return float((shape["pred_mean"] - shape["empirical"]).abs().mean())


def train_and_evaluate(dimension: str, holdout_frac: float | None = None) -> TrainResult:
    """Time-based (not random) train/holdout split by valid_date: the model must
    never see data from a date later than what it's evaluated on, since that's the
    real deployment condition (score today, resolve later)."""
    if holdout_frac is None:
        holdout_frac = load_config().models.holdout_frac
    df = load_dimension_frame(dimension)
    dates = sorted(df["valid_date"].unique())
    split_idx = max(1, round(len(dates) * (1 - holdout_frac)))
    train_dates, holdout_dates = dates[:split_idx], dates[split_idx:]
    if not holdout_dates:
        raise ValueError(f"Not enough distinct dates ({len(dates)}) to carve out a holdout split for {dimension}")

    train_df = df[df["valid_date"].isin(train_dates)]
    holdout_df = df[df["valid_date"].isin(holdout_dates)]

    model = build_model(dimension, FEATURE_COLUMNS)
    model.fit(train_df, train_df["target"])

    pred = model.predict_proba(holdout_df)
    baseline_rate = float(train_df["target"].mean())
    baseline_pred = np.full(len(holdout_df), baseline_rate)

    metrics = {
        "brier_score": float(brier_score_loss(holdout_df["target"], pred)),
        "brier_score_baseline": float(brier_score_loss(holdout_df["target"], baseline_pred)),
        "roc_auc": (
            float(roc_auc_score(holdout_df["target"], pred)) if holdout_df["target"].nunique() > 1 else float("nan")
        ),
        "train_positive_rate": baseline_rate,
        "holdout_positive_rate": float(holdout_df["target"].mean()),
        "lead_shape_mae": _lead_shape_mae(holdout_df, pred),
    }

    return TrainResult(
        dimension=dimension,
        model=model,
        feature_names=FEATURE_COLUMNS,
        metrics=metrics,
        train_window=(train_dates[0], train_dates[-1]),
        n_train_rows=len(train_df),
        n_holdout_rows=len(holdout_df),
    )
