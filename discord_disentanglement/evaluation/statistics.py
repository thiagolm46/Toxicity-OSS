"""Bootstrap reproduzível para estimativas escalares."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd


def bootstrap_confidence_interval(
    frame: pd.DataFrame,
    statistic: Callable[[pd.DataFrame], float],
    *,
    unit_column: str | None,
    resamples: int,
    confidence: float,
    seed: int,
) -> dict[str, Any]:
    estimate = float(statistic(frame)) if not frame.empty else 0.0
    if frame.empty or resamples == 0:
        return {
            "estimate": estimate,
            "lower": None,
            "upper": None,
            "confidence": confidence,
            "resamples": resamples,
            "unit": unit_column or "message",
            "seed": seed,
        }

    rng = np.random.default_rng(seed)
    samples: list[float] = []
    if unit_column is None:
        for _ in range(resamples):
            positions = rng.integers(0, len(frame), size=len(frame))
            samples.append(float(statistic(frame.iloc[positions].reset_index(drop=True))))
    else:
        work = frame.copy()
        work[unit_column] = work[unit_column].fillna("UNKNOWN").astype(str)
        units = work[unit_column].unique()
        groups = {unit: group for unit, group in work.groupby(unit_column, sort=False)}
        for _ in range(resamples):
            sampled_units = rng.choice(units, size=len(units), replace=True)
            pieces: list[pd.DataFrame] = []
            for replica, unit in enumerate(sampled_units):
                piece = groups[unit].copy()
                piece["_bootstrap_replica"] = replica
                pieces.append(piece)
            samples.append(float(statistic(pd.concat(pieces, ignore_index=True))))

    alpha = (1.0 - confidence) / 2.0
    return {
        "estimate": estimate,
        "lower": float(np.quantile(samples, alpha)),
        "upper": float(np.quantile(samples, 1.0 - alpha)),
        "confidence": confidence,
        "resamples": resamples,
        "unit": unit_column or "message",
        "seed": seed,
        "method": "percentile_bootstrap",
    }


def paired_bootstrap_difference(
    frame: pd.DataFrame,
    *,
    left_column: str,
    right_column: str,
    unit_column: str | None,
    resamples: int,
    confidence: float,
    seed: int,
) -> dict[str, Any]:
    """Confidence interval for a paired mean difference on shared examples."""
    required = {left_column, right_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Colunas ausentes no bootstrap pareado: " + ", ".join(sorted(missing)))
    work = frame.copy()
    work["_paired_difference"] = (
        work[left_column].astype(float) - work[right_column].astype(float)
    )
    estimate = float(work["_paired_difference"].mean()) if len(work) else 0.0
    samples: np.ndarray
    rng = np.random.default_rng(seed)
    if not len(work) or resamples == 0:
        samples = np.asarray([], dtype=float)
    elif unit_column is None:
        values = work["_paired_difference"].to_numpy(dtype=float)
        sampled_positions = rng.integers(
            0, len(values), size=(resamples, len(values))
        )
        samples = values[sampled_positions].mean(axis=1)
    else:
        grouped = work.assign(
            **{unit_column: work[unit_column].fillna("UNKNOWN").astype(str)}
        ).groupby(unit_column, sort=False)["_paired_difference"].agg(["sum", "count"])
        group_sums = grouped["sum"].to_numpy(dtype=float)
        group_counts = grouped["count"].to_numpy(dtype=float)
        sampled_groups = rng.integers(
            0, len(grouped), size=(resamples, len(grouped))
        )
        samples = group_sums[sampled_groups].sum(axis=1) / group_counts[
            sampled_groups
        ].sum(axis=1)
    alpha = (1.0 - confidence) / 2.0
    result = {
        "estimate": estimate,
        "lower": float(np.quantile(samples, alpha)) if len(samples) else None,
        "upper": float(np.quantile(samples, 1.0 - alpha)) if len(samples) else None,
        "confidence": confidence,
        "resamples": resamples,
        "unit": unit_column or "message",
        "seed": seed,
        "method": "paired_percentile_bootstrap",
    }
    result.update(
        {
            "estimand": "paired_mean_difference",
            "direction": f"{left_column} - {right_column}",
            "paired_example_count": int(len(work)),
        }
    )
    return result
