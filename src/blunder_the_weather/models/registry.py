"""Binds each dimension to a concrete ModelWrapper class, and the storage layout for
persisted model artifacts (both the local models/ mirror and MinIO). Swapping a
dimension to a different model class later is one line in _MODEL_CLASSES -- no
changes to training or serving code.
"""

from pathlib import Path

from blunder_the_weather.config import REPO_ROOT, load_config
from blunder_the_weather.models.base import ModelWrapper
from blunder_the_weather.models.linear import LogisticRegressionCalibratedModel

DIMENSIONS = ["temp_max", "temp_min", "cloud_cover", "humidity", "precip_chance"]

_MODEL_CLASSES: dict[str, type[ModelWrapper]] = {dimension: LogisticRegressionCalibratedModel for dimension in DIMENSIONS}


def build_model(dimension: str, feature_names: list[str]) -> ModelWrapper:
    models_config = load_config().models
    return _MODEL_CLASSES[dimension](
        feature_names=feature_names,
        calib_fraction=models_config.calib_fraction,
        class_weight=models_config.class_weight,
        random_state=models_config.random_state,
    )


def model_prefix(dimension: str, version: str) -> str:
    """MinIO key prefix -- the canonical, durable copy."""
    return f"models/{dimension}/{version}"


def local_model_dir(dimension: str, version: str) -> Path:
    """Local mirror under <repo_root>/models/ -- gitignored, convenient for
    inspection/serving without needing MinIO credentials on hand. MinIO remains the
    source of truth (see lakehouse/duckdb_query.py's "MinIO is the only persistent
    domain state" design); this is a cache, not a second source of truth."""
    return REPO_ROOT / "models" / dimension / version
