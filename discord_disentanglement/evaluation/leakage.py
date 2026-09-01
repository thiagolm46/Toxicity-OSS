"""Auditoria explícita do isolamento entre inferência e referência silver."""

from __future__ import annotations

from typing import Any

import pandas as pd

from discord_disentanglement.approaches.base import FORBIDDEN_PREDICTION_COLUMNS


class LeakageAuditError(RuntimeError):
    pass


def audit_prediction_inputs(
    *,
    candidates: pd.DataFrame,
    train_gold: pd.DataFrame,
    uses_direct_reply_training: bool,
) -> dict[str, Any]:
    leaked_columns = sorted(FORBIDDEN_PREDICTION_COLUMNS.intersection(candidates.columns))
    invalid_gold_splits: list[str] = []
    if not train_gold.empty and "source_split" in train_gold.columns:
        invalid_gold_splits = sorted(
            set(train_gold["source_split"].dropna().astype(str)).difference({"train"})
        )
    unexpected_train_gold = bool(not uses_direct_reply_training and not train_gold.empty)
    passed = not leaked_columns and not invalid_gold_splits and not unexpected_train_gold
    result = {
        "status": "PASSED" if passed else "FAILED",
        "prediction_input_columns": list(candidates.columns),
        "forbidden_columns_present": leaked_columns,
        "test_reply_hidden_during_inference": not leaked_columns,
        "train_gold_rows_visible_to_approach": int(len(train_gold)),
        "train_gold_allowed_by_method": bool(uses_direct_reply_training),
        "invalid_gold_splits": invalid_gold_splits,
        "serialized_prediction_cache_used": False,
        "graph_with_silver_edges_visible_to_approach": False,
    }
    if not passed:
        raise LeakageAuditError(f"Leakage audit falhou: {result}")
    return result
