"""Binds config/app.yaml's models.model_type to a concrete ModelWrapper class, and the
storage layout for persisted model artifacts (both the local models/ mirror and
MinIO). Swapping model types is a one-line config change -- no changes to training or
serving code. Each saved model's own meta.json records which class produced it (see
models/linear.py and models/xgboost_model.py), so load_model() always instantiates
the right class regardless of what the *current* config says -- a config flip doesn't
strand previously-trained models.
"""

import json
from pathlib import Path

import yaml
from dagster_aws.s3 import S3Resource

from blunder_the_weather.config import REPO_ROOT, load_config
from blunder_the_weather.lakehouse.io import download_dir_from_s3
from blunder_the_weather.models.base import ModelWrapper
from blunder_the_weather.models.linear import MODEL_TYPE as LOGISTIC_MODEL_TYPE
from blunder_the_weather.models.linear import LogisticRegressionCalibratedModel
from blunder_the_weather.models.xgboost_model import MODEL_TYPE as XGBOOST_MODEL_TYPE
from blunder_the_weather.models.xgboost_model import XGBoostCalibratedModel

DIMENSIONS = ["temp_max", "temp_min", "cloud_cover", "humidity", "precip_chance"]

_MODEL_CLASSES: dict[str, type[ModelWrapper]] = {
    LOGISTIC_MODEL_TYPE: LogisticRegressionCalibratedModel,
    XGBOOST_MODEL_TYPE: XGBoostCalibratedModel,
}

# Written by scripts/tune_hyperparameters.py's Bayesian search (models/tuning.py).
# Kept separate from config/app.yaml so a full rewrite of this file never touches the
# hand-maintained config's comments. Absence just means "no dimension tuned yet" --
# build_model() falls back to models.xgboost_default_params.
TUNED_PARAMS_PATH = REPO_ROOT / "config" / "tuned_hyperparams.yaml"


def _tuned_xgboost_params(dimension: str) -> dict[str, float | int] | None:
    if not TUNED_PARAMS_PATH.exists():
        return None
    with TUNED_PARAMS_PATH.open() as f:
        raw = yaml.safe_load(f) or {}
    return raw.get(dimension)


def build_model(dimension: str, feature_names: list[str]) -> ModelWrapper:
    models_config = load_config().models
    kwargs: dict = dict(
        feature_names=feature_names,
        calib_fraction=models_config.calib_fraction,
        class_weight=models_config.class_weight,
        random_state=models_config.random_state,
    )
    if models_config.model_type == XGBOOST_MODEL_TYPE:
        kwargs["xgboost_params"] = _tuned_xgboost_params(dimension) or models_config.xgboost_default_params
    return _MODEL_CLASSES[models_config.model_type](**kwargs)


def model_prefix(dimension: str, version: str) -> str:
    """MinIO key prefix -- the canonical, durable copy."""
    return f"models/{dimension}/{version}"


def local_model_dir(dimension: str, version: str) -> Path:
    """Local mirror under <repo_root>/models/ -- gitignored, convenient for
    inspection/serving without needing MinIO credentials on hand. MinIO remains the
    source of truth (see lakehouse/duckdb_query.py's "MinIO is the only persistent
    domain state" design); this is a cache, not a second source of truth."""
    return REPO_ROOT / "models" / dimension / version


def load_model(dimension: str, version: str, s3: S3Resource) -> ModelWrapper:
    """Loads a trained model for scoring, using the local mirror if training already
    ran on this machine and pulling from MinIO (the durable copy) otherwise. Which
    class to instantiate comes from the model's own meta.json, not the current
    config -- see module docstring."""
    local_dir = local_model_dir(dimension, version)
    if not local_dir.exists():
        local_dir.mkdir(parents=True, exist_ok=True)
        download_dir_from_s3(s3, model_prefix(dimension, version), local_dir)
    meta = json.loads((local_dir / "meta.json").read_text())
    # Models trained before model_type was recorded in meta.json were always
    # LogisticRegressionCalibratedModel -- that was the only class that existed.
    model_type = meta.get("model_type", LOGISTIC_MODEL_TYPE)
    return _MODEL_CLASSES[model_type].load(local_dir)
