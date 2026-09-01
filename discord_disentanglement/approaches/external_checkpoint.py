"""Carregamento estrito de checkpoints lineares treinados fora do Discord."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .base import ApproachContractError, PREDICTION_FEATURE_COLUMNS
from .math_utils import LogisticModel


@dataclass(frozen=True, slots=True)
class ExternalCheckpoint:
    path: Path
    sha256: str
    payload: dict[str, Any]
    model: LogisticModel


def load_external_checkpoint(path: Path, *, expected_approach_id: str) -> ExternalCheckpoint:
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise ApproachContractError(
            f"Checkpoint de {expected_approach_id} nao encontrado: {resolved}. "
            "Consulte docs/methodology/DISENTANGLEMENT_METHODS.md."
        )
    raw = resolved.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("approach_id") != expected_approach_id:
        raise ApproachContractError(
            f"Checkpoint pertence a {payload.get('approach_id')!r}, esperado {expected_approach_id!r}"
        )
    if tuple(payload.get("feature_columns", ())) != PREDICTION_FEATURE_COLUMNS:
        raise ApproachContractError("Checkpoint usa ordem de features incompatível")
    model_payload = payload.get("model", {})
    arrays = {
        name: np.asarray(model_payload.get(name, []), dtype=np.float64)
        for name in ("weights", "feature_mean", "feature_scale")
    }
    expected_size = len(PREDICTION_FEATURE_COLUMNS)
    if any(len(values) != expected_size for values in arrays.values()):
        raise ApproachContractError("Checkpoint possui dimensao de modelo invalida")
    model = LogisticModel(
        weights=arrays["weights"],
        bias=float(model_payload["bias"]),
        feature_mean=arrays["feature_mean"],
        feature_scale=arrays["feature_scale"],
    )
    return ExternalCheckpoint(
        path=resolved,
        sha256=hashlib.sha256(raw).hexdigest(),
        payload=payload,
        model=model,
    )
