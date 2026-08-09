"""Model interface: every dimension's classifier implements this Protocol, so
training and explanation code never need to know which algorithm sits underneath.
Swapping a dimension to a different model class later is a models/registry.py
config change, not a rewrite of any caller.
"""

from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
from pydantic import BaseModel


class ExplanationResult(BaseModel):
    """SHAP-style feature attributions, kept model-agnostic so a future PyTorch
    model's explain() returns the same shape."""

    feature_names: list[str]
    shap_values: list[list[float]]  # (n_rows, n_features)
    base_value: float


class ModelWrapper(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None: ...
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray: ...
    def explain(self, X: pd.DataFrame) -> ExplanationResult: ...
    def save(self, path: Path) -> None: ...

    @classmethod
    def load(cls, path: Path) -> "ModelWrapper": ...
