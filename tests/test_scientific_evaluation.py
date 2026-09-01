from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from discord_disentanglement.approaches import ApproachFitData, create_approach
from discord_disentanglement.approaches.base import PREDICTION_FEATURE_COLUMNS
from discord_disentanglement.approaches.base import ApproachContractError
from discord_disentanglement.evaluation.clustering import (
    projected_conversation_metrics,
    silver_projection,
)
from discord_disentanglement.evaluation.leakage import (
    LeakageAuditError,
    audit_prediction_inputs,
)
from discord_disentanglement.evaluation.ranking import (
    candidate_generation_metrics,
    ranking_metrics,
)
from discord_disentanglement.evaluation.statistics import (
    paired_bootstrap_difference,
)
from discord_disentanglement.training.external_irc import load_sessions


def _outcomes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_message_id": ["a", "b"],
            "channel_key": ["c1", "c1"],
            "candidate_count": [5, 5],
            "candidate_available": [True, False],
            "candidate_generation_rank": [2.0, np.nan],
            "rank_position": [1.0, np.nan],
            "hit_at_1": [1.0, 0.0],
            "hit_at_3": [1.0, 0.0],
            "hit_at_5": [1.0, 0.0],
            "hit_at_10": [1.0, 0.0],
            "reciprocal_rank": [1.0, 0.0],
        }
    )


def test_candidate_recall_and_overall_vs_conditional_ranking() -> None:
    outcomes = _outcomes()
    candidate = candidate_generation_metrics(outcomes, ks=(1, 2, 5))
    ranking = ranking_metrics(outcomes)

    assert candidate["candidate_recall"] == 0.5
    assert [point["candidate_recall"] for point in candidate["candidate_recall_by_k"]] == [
        0.0,
        0.5,
        0.5,
    ]
    assert ranking["overall"]["recall_at_1"] == 0.5
    assert ranking["overall"]["mrr"] == 0.5
    assert ranking["conditional"]["recall_at_1"] == 1.0
    assert ranking["conditional"]["mrr"] == 1.0


def test_projected_clustering_perfect_fragmentation_and_merge() -> None:
    perfect = pd.DataFrame(
        {
            "silver_thread_id": ["A", "A", "A", "B", "B"],
            "predicted_thread_id": ["P", "P", "P", "Q", "Q"],
        }
    )
    metrics = projected_conversation_metrics(perfect)
    assert metrics["ari"] == pytest.approx(1.0)
    assert metrics["nmi"] == pytest.approx(1.0)
    assert metrics["variation_of_information"] == pytest.approx(0.0)
    assert metrics["bcubed_f1"] == pytest.approx(1.0)
    assert metrics["exact_match"] == pytest.approx(1.0)
    assert metrics["fragmentation_rate"] == pytest.approx(0.0)
    assert metrics["merge_rate"] == pytest.approx(0.0)

    fragmented = perfect.copy()
    fragmented["predicted_thread_id"] = ["P1", "P1", "P2", "Q", "Q"]
    fragmented_metrics = projected_conversation_metrics(fragmented)
    assert fragmented_metrics["fragmentation_rate"] == pytest.approx(0.5)
    assert fragmented_metrics["merge_rate"] == pytest.approx(0.0)

    merged = perfect.copy()
    merged["predicted_thread_id"] = "ONE"
    merged_metrics = projected_conversation_metrics(merged)
    assert merged_metrics["fragmentation_rate"] == pytest.approx(0.0)
    assert merged_metrics["merge_rate"] == pytest.approx(1.0)
    assert merged_metrics["exact_match"] == pytest.approx(0.0)


def test_silver_projection_uses_only_explicit_reply_components() -> None:
    messages = pd.DataFrame(
        {
            "message_id": ["a1", "b1", "a2", "b2", "a3", "unknown"],
            "channel_key": ["c"] * 6,
            "channel_name": ["help"] * 6,
        }
    )
    gold = pd.DataFrame(
        {
            "source_message_id": ["a2", "a3", "b2"],
            "target_message_id": ["a1", "a2", "b1"],
            "source_split": ["train", "test", "test"],
        }
    )
    assignments = pd.DataFrame(
        {
            "message_id": messages["message_id"],
            "predicted_thread_id": ["P", "Q", "P", "Q", "P", "R"],
        }
    )
    projection = silver_projection(
        messages=messages,
        direct_reply_gold=gold,
        message_assignments=assignments,
    )
    assert set(projection["message_id"]) == {"a1", "a2", "a3", "b1", "b2"}
    assert "unknown" not in set(projection["message_id"])
    assert projection["silver_thread_id"].nunique() == 2


def test_leakage_audit_and_paired_bootstrap_are_explicit_and_deterministic() -> None:
    safe = pd.DataFrame({column: [0.0] for column in PREDICTION_FEATURE_COLUMNS})
    result = audit_prediction_inputs(
        candidates=safe,
        train_gold=pd.DataFrame(columns=["source_message_id", "target_message_id"]),
        uses_direct_reply_training=False,
    )
    assert result["status"] == "PASSED"
    with pytest.raises(LeakageAuditError):
        audit_prediction_inputs(
            candidates=safe.assign(referenced_message_id="m1"),
            train_gold=pd.DataFrame(),
            uses_direct_reply_training=False,
        )

    paired = pd.DataFrame(
        {
            "channel_key": ["c1", "c1", "c2", "c2"],
            "left": [1.0, 1.0, 0.0, 1.0],
            "right": [0.0, 1.0, 0.0, 0.0],
        }
    )
    kwargs = dict(
        left_column="left",
        right_column="right",
        unit_column="channel_key",
        resamples=100,
        confidence=0.95,
        seed=7,
    )
    first = paired_bootstrap_difference(paired, **kwargs)
    second = paired_bootstrap_difference(paired, **kwargs)
    assert first == second
    assert first["estimate"] == pytest.approx(0.5)
    assert first["unit"] == "channel_key"


@pytest.mark.parametrize("approach_id", ["chi_zero_shot", "irc_transfer"])
def test_external_adapter_contract_uses_no_discord_labels(approach_id: str) -> None:
    approach = create_approach(approach_id)
    empty = pd.DataFrame(columns=PREDICTION_FEATURE_COLUMNS)
    fit_data = ApproachFitData(
        train_candidates=empty,
        validation_candidates=empty,
        train_gold=pd.DataFrame(columns=["source_message_id", "target_message_id"]),
        random_seed=42,
    )
    approach.fit(fit_data)
    candidate = pd.DataFrame({column: [0.0] for column in PREDICTION_FEATURE_COLUMNS})
    score = approach.score(candidate)
    metadata = approach.manifest_metadata()

    assert len(score.scores) == 1
    assert np.isfinite(score.scores).all()
    assert metadata["implementation_type"] == "INSPIRED_BY"
    assert metadata["scientific_metadata"]["uses_discord_labels"] is False
    assert metadata["scientific_metadata"]["uses_direct_reply_train"] is False
    assert metadata["scientific_metadata"]["uses_direct_reply_test"] == "evaluation_only"


def test_external_adapter_fails_clearly_when_checkpoint_is_missing(tmp_path: Path) -> None:
    approach = create_approach(
        "chi_zero_shot", {"checkpoint_path": tmp_path / "missing.json"}
    )
    with pytest.raises(ApproachContractError, match="Checkpoint.*nao encontrado"):
        approach.preflight()


def test_irc_loader_preserves_official_raw_line_identifiers(tmp_path: Path) -> None:
    (tmp_path / "sample.ascii.txt").write_text(
        "[10:00] <alice> first\n"
        "=== bob has joined #ubuntu\n"
        "[10:01] <carol> middle\n"
        "=== bob is now known as robert\n"
        "[10:02] <bob> reply\n",
        encoding="utf-8",
    )
    (tmp_path / "sample.annotation.txt").write_text(
        "1000 1000 -\n1000 1004 -\n", encoding="utf-8"
    )
    labeled = load_sessions(tmp_path, include_annotations=True)
    unlabeled = load_sessions(tmp_path, include_annotations=False)

    assert [message.message_id for message in labeled[0].messages] == [1000, 1002, 1004]
    assert labeled[0].parents_by_child == {1000: (1000,), 1004: (1000,)}
    assert unlabeled[0].parents_by_child == {}
