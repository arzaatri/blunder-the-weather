"""Combines each dimension's calibrated error probability into one overall volatility
score per (point, valid_date, lead_days). Swappable via EnsembleStrategy so a smarter
combination later (e.g. per-dimension confidence weighting) is a models/registry.py
-style config change, not a rewrite of the scoring asset.
"""

from typing import Protocol

from blunder_the_weather.config import load_config
from blunder_the_weather.models.registry import DIMENSIONS


class EnsembleStrategy(Protocol):
    def combine(self, dimension_probs: dict[str, float]) -> float: ...


class WeightedAverageEnsemble:
    def __init__(self, weights: dict[str, float]):
        missing = set(DIMENSIONS) - set(weights)
        if missing:
            raise ValueError(f"Missing ensemble weights for dimensions: {sorted(missing)}")
        total = sum(weights.values())
        self._weights = {dimension: weight / total for dimension, weight in weights.items()}

    def combine(self, dimension_probs: dict[str, float]) -> float:
        missing = set(DIMENSIONS) - set(dimension_probs)
        if missing:
            raise ValueError(f"Missing predicted probabilities for dimensions: {sorted(missing)}")
        return sum(self._weights[dimension] * dimension_probs[dimension] for dimension in DIMENSIONS)


def build_ensemble() -> EnsembleStrategy:
    return WeightedAverageEnsemble(load_config().ensemble.weights)
