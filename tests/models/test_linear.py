import numpy as np
import pandas as pd
import pytest

from blunder_the_weather.models.linear import LogisticRegressionCalibratedModel

FEATURES = ["lead_days", "forecast_value"]


def _synthetic_frame(n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    lead_days = rng.integers(1, 8, size=n)
    forecast_value = rng.normal(0, 1, size=n)
    logit = 0.3 * lead_days - 2.0 * forecast_value - 2.0
    prob = 1 / (1 + np.exp(-logit))
    target = rng.binomial(1, prob)
    return pd.DataFrame({"lead_days": lead_days, "forecast_value": forecast_value, "target": target})


def test_fit_predict_proba_returns_valid_probabilities() -> None:
    df = _synthetic_frame()
    model = LogisticRegressionCalibratedModel(feature_names=FEATURES)
    model.fit(df, df["target"])

    proba = model.predict_proba(df)
    assert proba.shape == (len(df),)
    assert np.all((proba >= 0) & (proba <= 1))


def test_explain_matches_feature_count() -> None:
    df = _synthetic_frame()
    model = LogisticRegressionCalibratedModel(feature_names=FEATURES)
    model.fit(df, df["target"])

    explanation = model.explain(df.head(10))
    assert explanation.feature_names == FEATURES
    assert len(explanation.shap_values) == 10
    assert len(explanation.shap_values[0]) == len(FEATURES)


def test_save_and_load_round_trips_predictions(tmp_path) -> None:
    df = _synthetic_frame()
    model = LogisticRegressionCalibratedModel(feature_names=FEATURES)
    model.fit(df, df["target"])
    before = model.predict_proba(df)

    model.save(tmp_path)
    reloaded = LogisticRegressionCalibratedModel.load(tmp_path)
    after = reloaded.predict_proba(df)

    np.testing.assert_allclose(before, after)


def test_predict_proba_before_fit_raises() -> None:
    model = LogisticRegressionCalibratedModel(feature_names=FEATURES)
    with pytest.raises(RuntimeError):
        model.predict_proba(_synthetic_frame(n=5))
