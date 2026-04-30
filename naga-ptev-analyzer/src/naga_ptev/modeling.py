from __future__ import annotations

import json
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd

from naga_ptev.featurize import DEFAULT_RANK_POINTS, feature_columns_from_dataframe


TARGET_COLUMNS = ["p1", "p2", "p3", "p4"]


class NumpyRidgeRegressor:
    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = float(alpha)
        self.coef_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def fit(self, x: pd.DataFrame, y: pd.DataFrame) -> "NumpyRidgeRegressor":
        x_values = np.asarray(x, dtype=float)
        y_values = np.asarray(y, dtype=float)
        self.mean_ = x_values.mean(axis=0)
        scale = x_values.std(axis=0)
        scale[scale == 0] = 1.0
        self.scale_ = scale
        normalized_x = (x_values - self.mean_) / self.scale_
        design = np.column_stack([np.ones(len(normalized_x)), normalized_x])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coef_ = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y_values
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        if self.coef_ is None or self.mean_ is None or self.scale_ is None:
            raise RuntimeError("model is not fitted")
        x_values = np.asarray(x, dtype=float)
        normalized_x = (x_values - self.mean_) / self.scale_
        design = np.column_stack([np.ones(len(normalized_x)), normalized_x])
        return design @ self.coef_


class RankProbabilityModel:
    def __init__(self, model: Any, feature_columns: list[str], model_name: str) -> None:
        self.model = model
        self.feature_columns = list(feature_columns)
        self.model_name = str(model_name)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        raw = np.asarray(self.model.predict(df[self.feature_columns]), dtype=float)
        if raw.ndim == 1:
            raw = raw.reshape(-1, 4)
        return normalize_probabilities(raw)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.predict_proba(df)


def normalize_probabilities(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(values, dtype=float), 0.0, None)
    sums = clipped.sum(axis=1, keepdims=True)
    return np.divide(clipped, sums, out=np.full_like(clipped, 0.25), where=sums > 0)


def ptev_from_probabilities(probabilities: np.ndarray) -> np.ndarray:
    return np.asarray(probabilities, dtype=float).dot(np.asarray(DEFAULT_RANK_POINTS, dtype=float))


def _build_estimator(model_name: str) -> Any:
    normalized = str(model_name or "histgb").strip().lower()
    if normalized in {"histgb", "hist_gradient_boosting"}:
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.multioutput import MultiOutputRegressor

        return MultiOutputRegressor(HistGradientBoostingRegressor(random_state=1))
    if normalized in {"rf", "randomforest", "random_forest"}:
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(n_estimators=200, random_state=1, n_jobs=-1, min_samples_leaf=2)
    if normalized in {"ridge", "linear"}:
        try:
            from sklearn.multioutput import MultiOutputRegressor
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.linear_model import Ridge
        except ImportError:
            return NumpyRidgeRegressor(alpha=1.0)

        return MultiOutputRegressor(make_pipeline(StandardScaler(), Ridge(alpha=1.0)))
    if normalized in {"lgbm", "lightgbm"}:
        try:
            from lightgbm import LGBMRegressor
            from sklearn.multioutput import MultiOutputRegressor
        except ImportError as exc:
            raise RuntimeError("LightGBM is not installed. Use --model histgb/rf/ridge or install lightgbm.") from exc

        return MultiOutputRegressor(LGBMRegressor(random_state=1, n_estimators=300))
    raise ValueError(f"Unknown model: {model_name}")


def train_model(
    *,
    dataset: str | Path,
    model_name: str = "histgb",
    out: str | Path = "artifacts/models",
) -> RankProbabilityModel:
    df = pd.read_csv(dataset)
    if df.empty:
        raise RuntimeError("dataset is empty")
    feature_columns = feature_columns_from_dataframe(df)
    estimator = _build_estimator(model_name)
    estimator.fit(df[feature_columns], df[TARGET_COLUMNS])
    wrapped = RankProbabilityModel(estimator, feature_columns, model_name)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "model.pkl").open("wb") as handle:
        pickle.dump(wrapped, handle)
    (out_dir / "feature_columns.json").write_text(json.dumps(feature_columns, indent=2), encoding="utf-8")
    return wrapped


def load_model(path: str | Path) -> RankProbabilityModel:
    with Path(path).open("rb") as handle:
        loaded = pickle.load(handle)
    if not isinstance(loaded, RankProbabilityModel):
        raise TypeError(f"Unsupported model artifact: {type(loaded).__name__}")
    return loaded
