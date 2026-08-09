"""Calibrated logistic regression: the initial concrete ModelWrapper, used by all
four dimensions to start. Swapping one dimension to a different model class later
(e.g. PyTorch) is a models/registry.py change, not a rewrite of training code.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from joblib import dump, load
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from blunder_the_weather.models.base import ExplanationResult


class LogisticRegressionCalibratedModel:
    """fit() internally carves out a stratified calibration split from X/y (rather
    than requiring the caller to pass one) and fits a plain LogisticRegression on
    the remainder, then wraps it (frozen, via sklearn's FrozenEstimator) with
    CalibratedClassifierCV on the calibration split. This keeps a single, unambiguous
    base model for SHAP -- calibration is a monotonic reshaping of its output, so it
    doesn't change feature-attribution ranking. Feature scaling is fit alongside and
    applied consistently at predict/explain time.
    """

    def __init__(
        self,
        feature_names: list[str],
        calib_fraction: float = 0.2,
        class_weight: str | None = "balanced",
        random_state: int = 0,
    ):
        self.feature_names = feature_names
        self.calib_fraction = calib_fraction
        self.random_state = random_state
        self._scaler = StandardScaler()
        self._base = LogisticRegression(class_weight=class_weight, random_state=random_state, max_iter=1000)
        self._calibrated: CalibratedClassifierCV | None = None
        self._background: np.ndarray | None = None
        self._explainer: shap.LinearExplainer | None = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        X_base, X_calib, y_base, y_calib = train_test_split(
            X[self.feature_names], y, test_size=self.calib_fraction, random_state=self.random_state, stratify=y
        )
        X_base_scaled = self._scaler.fit_transform(X_base)
        self._base.fit(X_base_scaled, y_base)
        self._calibrated = CalibratedClassifierCV(FrozenEstimator(self._base), method="sigmoid")
        self._calibrated.fit(self._scaler.transform(X_calib), y_calib)
        # Cap the SHAP background sample at shap's own default max_samples, so
        # persisted models stay small and shap doesn't re-subsample (with a warning)
        # on every explain() call -- it only needs this to estimate feature
        # means/covariance, not the full training set.
        self._background = X_base_scaled[:100]
        self._explainer = shap.LinearExplainer(self._base, self._background)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self._calibrated is None:
            raise RuntimeError("Model not fit yet")
        return self._calibrated.predict_proba(self._scaler.transform(X[self.feature_names]))[:, 1]

    def explain(self, X: pd.DataFrame) -> ExplanationResult:
        if self._explainer is None:
            raise RuntimeError("Model not fit yet")
        values = self._explainer.shap_values(self._scaler.transform(X[self.feature_names]))
        return ExplanationResult(
            feature_names=self.feature_names,
            shap_values=np.asarray(values).tolist(),
            base_value=float(np.asarray(self._explainer.expected_value).reshape(-1)[0]),
        )

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        dump(self._scaler, path / "scaler.joblib")
        dump(self._base, path / "base.joblib")
        dump(self._calibrated, path / "calibrated.joblib")
        dump(self._background, path / "background.joblib")
        (path / "meta.json").write_text(json.dumps({"feature_names": self.feature_names}))

    @classmethod
    def load(cls, path: Path) -> "LogisticRegressionCalibratedModel":
        meta = json.loads((path / "meta.json").read_text())
        model = cls(feature_names=meta["feature_names"])
        model._scaler = load(path / "scaler.joblib")
        model._base = load(path / "base.joblib")
        model._calibrated = load(path / "calibrated.joblib")
        model._background = load(path / "background.joblib")
        model._explainer = shap.LinearExplainer(model._base, model._background)
        return model
