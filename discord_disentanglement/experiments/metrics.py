from __future__ import annotations

from typing import Any

import pandas as pd


def compute_test_metrics(
    *,
    approach_id: str,
    ranked_candidates: pd.DataFrame,
    predicted_links: pd.DataFrame,
    message_assignments: pd.DataFrame,
    direct_reply_gold: pd.DataFrame,
    selection_threshold: float,
    abstention_quantile: float,
) -> dict[str, Any]:
    """Evaluate only sources in the chronologically held-out test split.

    Explicit replies are a positive-only silver reference: non-reply messages are not
    treated as true negatives because they may still belong to an earlier message.
    """

    test_ranked = ranked_candidates[ranked_candidates["source_split"] == "test"]
    test_links = predicted_links[predicted_links["source_split"] == "test"]
    test_assignments = message_assignments[message_assignments["split"] == "test"]
    gold_test = direct_reply_gold[direct_reply_gold["source_split"] == "test"]
    gold_count = len(gold_test)

    recovered = gold_test.merge(
        test_ranked[
            ["source_message_id", "target_message_id", "rank_position", "score"]
        ],
        on=["source_message_id", "target_message_id"],
        how="inner",
        validate="one_to_one",
    )
    reciprocal_rank_sum = (
        float((1.0 / recovered["rank_position"].astype(float)).sum())
        if not recovered.empty
        else 0.0
    )
    selected_on_gold_sources = gold_test.merge(
        test_links[["source_message_id", "target_message_id", "score"]],
        on="source_message_id",
        how="left",
        suffixes=("_gold", "_predicted"),
        validate="one_to_one",
    )
    correct_selected = int(
        (
            selected_on_gold_sources["target_message_id_gold"]
            == selected_on_gold_sources["target_message_id_predicted"]
        ).sum()
    ) if not selected_on_gold_sources.empty else 0

    test_thread_sizes = (
        test_assignments.groupby("predicted_thread_id", sort=False)
        .size()
        .astype(float)
    )
    test_message_count = int(len(test_assignments))
    if test_links.empty:
        cross_channel_link_count = 0
        non_past_link_count = 0
    else:
        source_channel = test_links["channel_id"].fillna("").astype(str)
        target_channel = test_links["target_channel_id"].fillna("").astype(str)
        source_channel = source_channel.where(
            source_channel.ne(""),
            "name:" + test_links["channel_name"].fillna("").astype(str).str.casefold(),
        )
        target_channel = target_channel.where(
            target_channel.ne(""),
            "name:"
            + test_links["target_channel_name"].fillna("").astype(str).str.casefold(),
        )
        cross_channel_link_count = int(source_channel.ne(target_channel).sum())
        non_past_link_count = int((test_links["delta_seconds"] <= 0).sum())
    return {
        "approach_id": approach_id,
        "evaluation_split": "test",
        "scope": "held_out_test_only",
        "reference_status": "explicit_replies_are_positive_only_silver_labels",
        "selection_threshold": float(selection_threshold),
        "threshold_calibration": "label_free_validation_best_score_quantile",
        "validation_abstention_quantile": float(abstention_quantile),
        "test_message_count": test_message_count,
        "test_candidate_pair_count": int(len(test_ranked)),
        "test_candidate_source_count": int(test_ranked["source_message_id"].nunique()),
        "test_predicted_link_count": int(len(test_links)),
        "test_cross_channel_predicted_link_count": cross_channel_link_count,
        "test_non_past_predicted_link_count": non_past_link_count,
        "test_link_selection_rate": (
            float(len(test_links) / max(1, test_ranked["source_message_id"].nunique()))
        ),
        "test_explicit_reply_count": int(gold_count),
        "test_explicit_reply_candidate_coverage": (
            float(len(recovered) / gold_count) if gold_count else 0.0
        ),
        "test_recall_at_1": (
            float((recovered["rank_position"] <= 1).sum() / gold_count)
            if gold_count
            else 0.0
        ),
        "test_recall_at_3": (
            float((recovered["rank_position"] <= 3).sum() / gold_count)
            if gold_count
            else 0.0
        ),
        "test_recall_at_5": (
            float((recovered["rank_position"] <= 5).sum() / gold_count)
            if gold_count
            else 0.0
        ),
        "test_mrr": float(reciprocal_rank_sum / gold_count) if gold_count else 0.0,
        "test_selected_parent_accuracy_on_explicit_sources": (
            float(correct_selected / gold_count) if gold_count else 0.0
        ),
        "test_predicted_thread_count": int(test_assignments["predicted_thread_id"].nunique()),
        "test_mean_test_partition_messages_per_predicted_thread": (
            float(test_thread_sizes.mean()) if not test_thread_sizes.empty else 0.0
        ),
        "test_partition_singleton_assignment_rate": (
            float(
                test_assignments["predicted_thread_id"]
                .map(test_thread_sizes)
                .eq(1)
                .sum()
                / test_message_count
            )
            if test_message_count
            else 0.0
        ),
        "limitations": [
            "Somente replies explicitos held-out sao usados como referencia positiva.",
            "Ausencia de reply explicito nao implica link negativo.",
            "IDs de thread nativa nao entram em features nem na avaliacao principal.",
        ],
    }
