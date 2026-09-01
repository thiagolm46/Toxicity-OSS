"""Orquestra a avaliação comum sem conhecer detalhes das abordagens."""

from __future__ import annotations

from typing import Any

import pandas as pd

from discord_disentanglement.evaluation.clustering import (
    projected_conversation_metrics,
    silver_projection,
)
from discord_disentanglement.evaluation.ranking import (
    build_gold_outcomes,
    candidate_generation_metrics,
    ranking_metrics,
    stratified_metrics,
)
from discord_disentanglement.evaluation.statistics import bootstrap_confidence_interval

from .config import ExperimentConfig


def compute_test_metrics(
    *,
    approach_id: str,
    ranked_candidates: pd.DataFrame,
    predicted_links: pd.DataFrame,
    message_assignments: pd.DataFrame,
    direct_reply_gold: pd.DataFrame,
    messages: pd.DataFrame,
    selection_threshold: float,
    config: ExperimentConfig,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Avalia replies e clusters apenas após a inferência mascarada."""
    test_ranked = ranked_candidates[ranked_candidates["source_split"] == "test"]
    test_links = predicted_links[predicted_links["source_split"] == "test"]
    test_assignments = message_assignments[message_assignments["split"] == "test"]
    outcomes = build_gold_outcomes(ranked_candidates, direct_reply_gold, messages)
    projection = silver_projection(
        messages=messages,
        direct_reply_gold=direct_reply_gold,
        message_assignments=message_assignments,
    )

    candidate_metrics = candidate_generation_metrics(
        outcomes, ks=config.candidate_recall_ks
    )
    ranking = ranking_metrics(outcomes)
    reconstruction = projected_conversation_metrics(projection)
    stratified = stratified_metrics(
        outcomes,
        parent_boundaries=config.parent_distance_boundaries,
        time_boundaries=config.time_gap_boundaries_seconds,
        competition_low_max=config.competition_low_max,
        competition_high_min=config.competition_high_min,
    )
    bootstrap_unit_column = "channel_key" if config.bootstrap_unit == "channel" else None
    statistics = {
        "unit_of_analysis": config.bootstrap_unit,
        "resamples": config.bootstrap_resamples,
        "confidence": config.bootstrap_confidence,
        "seed": config.random_seed,
        "intervals": {
            "recall_at_1_overall": bootstrap_confidence_interval(
                outcomes,
                lambda frame: float(frame["hit_at_1"].mean()) if len(frame) else 0.0,
                unit_column=bootstrap_unit_column,
                resamples=config.bootstrap_resamples,
                confidence=config.bootstrap_confidence,
                seed=config.random_seed,
            ),
            "mrr_overall": bootstrap_confidence_interval(
                outcomes,
                lambda frame: float(frame["reciprocal_rank"].mean()) if len(frame) else 0.0,
                unit_column=bootstrap_unit_column,
                resamples=config.bootstrap_resamples,
                confidence=config.bootstrap_confidence,
                seed=config.random_seed + 1,
            ),
            "bcubed_f1": bootstrap_confidence_interval(
                projection,
                lambda frame: float(projected_conversation_metrics(frame)["bcubed_f1"] or 0.0),
                unit_column=("channel_key" if config.bootstrap_unit == "channel" else None),
                resamples=config.bootstrap_resamples,
                confidence=config.bootstrap_confidence,
                seed=config.random_seed + 2,
            ),
            "ari": bootstrap_confidence_interval(
                projection,
                lambda frame: float(projected_conversation_metrics(frame)["ari"] or 0.0),
                unit_column=("channel_key" if config.bootstrap_unit == "channel" else None),
                resamples=config.bootstrap_resamples,
                confidence=config.bootstrap_confidence,
                seed=config.random_seed + 3,
            ),
        },
    }

    cross_channel_count, non_past_count = _link_invariants(test_links)
    thread_sizes = test_assignments.groupby("predicted_thread_id", sort=False).size()
    message_count = len(test_assignments)
    metrics: dict[str, Any] = {
        "schema_version": "2.0",
        "approach_id": approach_id,
        "evaluation_split": "test",
        "scope": "held_out_test_only",
        "reference_status": "partial_silver_explicit_discord_replies",
        "candidate_generation": candidate_metrics,
        "ranking": ranking,
        "conversation_reconstruction": reconstruction,
        "stratified": stratified,
        "statistics": statistics,
        "link_selection": {
            "selection_threshold": float(selection_threshold),
            "threshold_calibration": "label_free_validation_best_score_quantile",
            "validation_abstention_quantile": float(config.validation_abstention_quantile),
            "predicted_link_count": int(len(test_links)),
            "candidate_source_count": int(test_ranked["source_message_id"].nunique()),
            "selection_rate": float(
                len(test_links) / max(1, test_ranked["source_message_id"].nunique())
            ),
            "cross_channel_link_count": cross_channel_count,
            "non_past_link_count": non_past_count,
        },
        "predicted_partition": {
            "test_message_count": int(message_count),
            "test_predicted_thread_count": int(test_assignments["predicted_thread_id"].nunique()),
            "mean_test_messages_per_predicted_thread": (
                float(thread_sizes.mean()) if not thread_sizes.empty else 0.0
            ),
            "singleton_assignment_rate": (
                float(test_assignments["predicted_thread_id"].map(thread_sizes).eq(1).mean())
                if message_count
                else 0.0
            ),
        },
        "limitations": [
            "direct_reply observa apenas relacoes positivas e parciais.",
            "ausencia de direct_reply significa relacao desconhecida, nao negativa.",
            "Candidate Recall limita o teto das metricas de ranking.",
            "clusters sao avaliados somente apos projecao sobre mensagens silver-evaluable.",
        ],
    }
    # Aliases versionados para leitores do schema 1.x. A fonte autoritativa do
    # schema 2.0 continua sendo os blocos aninhados acima.
    metrics.update(
        {
            "selection_threshold": float(selection_threshold),
            "test_message_count": int(message_count),
            "test_cross_channel_predicted_link_count": cross_channel_count,
            "test_non_past_predicted_link_count": non_past_count,
        }
    )
    return metrics, outcomes, projection


def _link_invariants(links: pd.DataFrame) -> tuple[int, int]:
    if links.empty:
        return 0, 0
    source = links["channel_id"].fillna("").astype(str)
    target = links["target_channel_id"].fillna("").astype(str)
    source = source.where(
        source.ne(""), "name:" + links["channel_name"].fillna("").astype(str).str.casefold()
    )
    target = target.where(
        target.ne(""),
        "name:" + links["target_channel_name"].fillna("").astype(str).str.casefold(),
    )
    return int(source.ne(target).sum()), int((links["delta_seconds"] <= 0).sum())
