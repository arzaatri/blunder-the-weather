"""Runs models/tuning.py's Bayesian hyperparameter search for every dimension's
XGBoost model and writes the results to config/tuned_hyperparams.yaml, which
models/registry.py's build_model() reads automatically on the next training run.

Usage: uv run python scripts/tune_hyperparameters.py [n_trials]
"""

import sys

import yaml

from blunder_the_weather.models.registry import DIMENSIONS, TUNED_PARAMS_PATH
from blunder_the_weather.models.tuning import tune_dimension


def main() -> None:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 25

    results: dict[str, dict[str, float | int]] = {}
    for dimension in DIMENSIONS:
        print(f"Tuning {dimension} ({n_trials} trials)...")
        result = tune_dimension(dimension, n_trials=n_trials)
        print(f"  best holdout Brier score: {result.best_brier:.4f}  params: {result.best_params}")
        results[dimension] = result.best_params

    with TUNED_PARAMS_PATH.open("w") as f:
        yaml.safe_dump(results, f, sort_keys=False)
    print(f"Wrote tuned hyperparameters to {TUNED_PARAMS_PATH}")


if __name__ == "__main__":
    main()
