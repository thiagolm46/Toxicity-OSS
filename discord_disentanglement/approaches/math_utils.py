from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class LogisticModel:
    weights: np.ndarray
    bias: float
    feature_mean: np.ndarray
    feature_scale: np.ndarray

    def decision_function(self, features: np.ndarray) -> np.ndarray:
        if features.size == 0:
            return np.empty(0, dtype=np.float64)
        standardized = (features - self.feature_mean) / self.feature_scale
        return standardized @ self.weights + self.bias

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        return sigmoid(self.decision_function(features))


def fit_logistic_regression(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    sample_weight: np.ndarray | None = None,
    epochs: int = 160,
    learning_rate: float = 0.12,
    l2_penalty: float = 1e-3,
) -> LogisticModel:
    """Small deterministic batch logistic regression with no external model download."""

    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0]:
        raise ValueError("features/labels com dimensoes incompativeis")
    if x.shape[0] == 0:
        raise ValueError("nao ha exemplos para ajustar regressao logistica")
    unique_labels = set(np.unique(y).tolist())
    if unique_labels != {0.0, 1.0}:
        raise ValueError("regressao logistica requer exemplos positivos e negativos")

    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    standardized = (x - mean) / scale
    weights = np.zeros(x.shape[1], dtype=np.float64)
    positive_count = max(1, int((y == 1.0).sum()))
    negative_count = max(1, int((y == 0.0).sum()))
    balanced = np.where(
        y == 1.0,
        x.shape[0] / (2.0 * positive_count),
        x.shape[0] / (2.0 * negative_count),
    )
    weights_per_example = balanced if sample_weight is None else balanced * sample_weight
    normalizer = max(float(weights_per_example.sum()), 1.0)
    bias = 0.0

    for _ in range(epochs):
        probabilities = sigmoid(standardized @ weights + bias)
        errors = (probabilities - y) * weights_per_example
        gradient = (standardized.T @ errors) / normalizer + l2_penalty * weights
        bias_gradient = float(errors.sum()) / normalizer
        weights -= learning_rate * gradient
        bias -= learning_rate * bias_gradient

    return LogisticModel(
        weights=weights,
        bias=float(bias),
        feature_mean=mean,
        feature_scale=scale,
    )


def sigmoid(values: np.ndarray | float) -> np.ndarray:
    clipped = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def deterministic_subsample_indices(length: int, maximum: int) -> np.ndarray:
    """Evenly spaced sample that is stable and keeps the chronological range."""

    if length <= maximum:
        return np.arange(length, dtype=np.int64)
    return np.linspace(0, length - 1, num=maximum, dtype=np.int64)
