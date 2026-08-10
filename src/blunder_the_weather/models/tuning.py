"""Small Bayesian hyperparameter search for the XGBoost models, using optuna's
default TPE (Tree-structured Parzen Estimator) sampler -- a standard sequential
Bayesian optimization method: each trial's parameters are chosen from a probabilistic
model fit on prior trials' results, rather than a fixed grid or pure random search.

Reuses the exact same time-based train/holdout split as models/training.py's
train_and_evaluate(), rather than introducing k-fold CV just for tuning -- keeps the
tuning objective methodologically consistent with how models are actually evaluated.
"""

from dataclasses import dataclass

import optuna
from sklearn.metrics import brier_score_loss

from blunder_the_weather.config import load_config
from blunder_the_weather.models.features import FEATURE_COLUMNS, load_dimension_frame
from blunder_the_weather.models.xgboost_model import XGBoostCalibratedModel

optuna.logging.set_verbosity(optuna.logging.WARNING)

_SEARCH_SPACE = {
    "n_estimators": (50, 400),
    "max_depth": (2, 6),
    "learning_rate": (0.01, 0.3),
    "subsample": (0.5, 1.0),
    "colsample_bytree": (0.5, 1.0),
    "reg_alpha": (1e-8, 1.0),
    "reg_lambda": (1e-8, 10.0),
}


@dataclass
class TuneResult:
    dimension: str
    best_params: dict[str, float | int]
    best_brier: float
    n_trials: int


def _suggest_params(trial: optuna.Trial) -> dict[str, float | int]:
    return {
        "n_estimators": trial.suggest_int("n_estimators", *_SEARCH_SPACE["n_estimators"]),
        "max_depth": trial.suggest_int("max_depth", *_SEARCH_SPACE["max_depth"]),
        "learning_rate": trial.suggest_float("learning_rate", *_SEARCH_SPACE["learning_rate"], log=True),
        "subsample": trial.suggest_float("subsample", *_SEARCH_SPACE["subsample"]),
        "colsample_bytree": trial.suggest_float("colsample_bytree", *_SEARCH_SPACE["colsample_bytree"]),
        "reg_alpha": trial.suggest_float("reg_alpha", *_SEARCH_SPACE["reg_alpha"], log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", *_SEARCH_SPACE["reg_lambda"], log=True),
    }


def tune_dimension(dimension: str, n_trials: int = 25) -> TuneResult:
    models_config = load_config().models
    df = load_dimension_frame(dimension)
    dates = sorted(df["valid_date"].unique())
    split_idx = max(1, round(len(dates) * (1 - models_config.holdout_frac)))
    train_dates, holdout_dates = dates[:split_idx], dates[split_idx:]
    if not holdout_dates:
        raise ValueError(f"Not enough distinct dates ({len(dates)}) to tune {dimension}")

    train_df = df[df["valid_date"].isin(train_dates)]
    holdout_df = df[df["valid_date"].isin(holdout_dates)]

    def objective(trial: optuna.Trial) -> float:
        model = XGBoostCalibratedModel(
            feature_names=FEATURE_COLUMNS,
            calib_fraction=models_config.calib_fraction,
            class_weight=models_config.class_weight,
            random_state=models_config.random_state,
            xgboost_params=_suggest_params(trial),
        )
        model.fit(train_df, train_df["target"])
        pred = model.predict_proba(holdout_df)
        return brier_score_loss(holdout_df["target"], pred)

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=models_config.random_state))
    study.optimize(objective, n_trials=n_trials)

    return TuneResult(dimension=dimension, best_params=study.best_params, best_brier=study.best_value, n_trials=n_trials)
