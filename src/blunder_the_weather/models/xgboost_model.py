"""Calibrated XGBoost classifier: a second concrete ModelWrapper, swappable with
LogisticRegressionCalibratedModel via config/app.yaml's models.model_type. Tree
models don't need feature scaling, so this skips models/linear.py's StandardScaler
step; SHAP uses shap.TreeExplainer's exact tree_path_dependent mode (no background
sample needed) instead of LinearExplainer.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from joblib import dump, load
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from blunder_the_weather.models.base import ExplanationResult

MODEL_TYPE = "xgboost"


class XGBoostCalibratedModel:
    """Same internal calibration-split pattern as LogisticRegressionCalibratedModel
    (models/linear.py): fit() carves out a stratified calibration split, fits a plain
    XGBClassifier on the remainder, then wraps it (frozen) with CalibratedClassifierCV
    so there's one unambiguous base model for SHAP.
    """

    def __init__(
        self,
        feature_names: list[str],
        calib_fraction: float = 0.2,
        class_weight: str | None = "balanced",
        random_state: int = 0,
        xgboost_params: dict[str, float | int] | None = None,
    ):
        self.feature_names = feature_names
        self.calib_fraction = calib_fraction
        self.class_weight = class_weight
        self.random_state = random_state
        self.xgboost_params = dict(xgboost_params or {})
        self._base: XGBClassifier | None = None
        self._calibrated: CalibratedClassifierCV | None = None
        self._explainer: shap.TreeExplainer | None = None

    def _build_base(self, y: pd.Series) -> XGBClassifier:
        params: dict[str, float | int] = {"random_state": self.random_state, "eval_metric": "logloss"}
        params.update(self.xgboost_params)
        # XGBoost has no class_weight param -- scale_pos_weight is its equivalent for
        # binary classification, so "balanced" is translated the same way sklearn's
        # class_weight="balanced" would (inverse class frequency ratio).
        if self.class_weight == "balanced":
            positive = int(y.sum())
            negative = len(y) - positive
            params.setdefault("scale_pos_weight", negative / positive if positive else 1.0)
        return XGBClassifier(**params)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        X_base, X_calib, y_base, y_calib = train_test_split(
            X[self.feature_names], y, test_size=self.calib_fraction, random_state=self.random_state, stratify=y
        )
        self._base = self._build_base(y_base)
        self._base.fit(X_base, y_base)
        self._calibrated = CalibratedClassifierCV(FrozenEstimator(self._base), method="sigmoid")
        self._calibrated.fit(X_calib, y_calib)
        self._explainer = shap.TreeExplainer(self._base)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self._calibrated is None:
            raise RuntimeError("Model not fit yet")
        return self._calibrated.predict_proba(X[self.feature_names])[:, 1]

    def explain(self, X: pd.DataFrame) -> ExplanationResult:
        if self._explainer is None:
            raise RuntimeError("Model not fit yet")
        values = self._explainer.shap_values(X[self.feature_names])
        return ExplanationResult(
            feature_names=self.feature_names,
            shap_values=np.asarray(values).tolist(),
            base_value=float(np.asarray(self._explainer.expected_value).reshape(-1)[0]),
        )

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._base.save_model(path / "base.json")
        dump(self._calibrated, path / "calibrated.joblib")
        (path / "meta.json").write_text(json.dumps({"feature_names": self.feature_names, "model_type": MODEL_TYPE}))

    @classmethod
    def load(cls, path: Path) -> "XGBoostCalibratedModel":
        meta = json.loads((path / "meta.json").read_text())
        model = cls(feature_names=meta["feature_names"])
        model._base = XGBClassifier()
        model._base.load_model(path / "base.json")
        model._calibrated = load(path / "calibrated.joblib")
        model._explainer = shap.TreeExplainer(model._base)
        return model
