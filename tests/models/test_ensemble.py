import pytest

from blunder_the_weather.models.ensemble import WeightedAverageEnsemble
from blunder_the_weather.models.registry import DIMENSIONS


def test_equal_weights_average_matches_plain_mean() -> None:
    ensemble = WeightedAverageEnsemble({d: 1.0 for d in DIMENSIONS})
    probs = {d: p for d, p in zip(DIMENSIONS, [0.1, 0.2, 0.3, 0.4, 0.5])}

    assert ensemble.combine(probs) == pytest.approx(sum(probs.values()) / len(probs))


def test_unnormalized_weights_are_normalized_internally() -> None:
    # All weight on one dimension, zero on the rest -- normalization should make this
    # equivalent to just returning that dimension's probability.
    weights = {d: 0.0 for d in DIMENSIONS}
    weights[DIMENSIONS[0]] = 10.0
    ensemble = WeightedAverageEnsemble(weights)

    probs = {d: p for d, p in zip(DIMENSIONS, [0.9, 0.1, 0.1, 0.1, 0.1])}
    assert ensemble.combine(probs) == pytest.approx(0.9)


def test_missing_weight_raises() -> None:
    weights = {d: 1.0 for d in DIMENSIONS[:-1]}
    with pytest.raises(ValueError, match="Missing ensemble weights"):
        WeightedAverageEnsemble(weights)


def test_missing_prediction_raises() -> None:
    ensemble = WeightedAverageEnsemble({d: 1.0 for d in DIMENSIONS})
    probs = {d: 0.5 for d in DIMENSIONS[:-1]}
    with pytest.raises(ValueError, match="Missing predicted probabilities"):
        ensemble.combine(probs)
