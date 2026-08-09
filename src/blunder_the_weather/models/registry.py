"""Binds each dimension to a concrete ModelWrapper class, and the MinIO layout for
persisted model artifacts. Swapping a dimension to a different model class later is
one line in _MODEL_CLASSES -- no changes to training or serving code.
"""

from blunder_the_weather.config import load_config
from blunder_the_weather.models.base import ModelWrapper
from blunder_the_weather.models.linear import LogisticRegressionCalibratedModel

DIMENSIONS = ["temp_max", "cloud_cover", "humidity", "precip_chance"]

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
    return f"models/{dimension}/{version}"
