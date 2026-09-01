"""Métricas que separam geração de candidatos e ordenação."""

from __future__ import annotations

from typing import Any

import pandas as pd


def build_gold_outcomes(
    ranked_candidates: pd.DataFrame,
    direct_reply_gold: pd.DataFrame,
    messages: pd.DataFrame,
) -> pd.DataFrame:
    gold = direct_reply_gold[direct_reply_gold["source_split"] == "test"].copy()
    gold.rename(columns={"target_message_id": "silver_parent_message_id"}, inplace=True)
    message_index = messages.set_index("message_id", drop=False)
    candidate_counts = (
        ranked_candidates[ranked_candidates["source_split"] == "test"]
        .groupby("source_message_id", sort=False)
        .size()
    )
    test_ranking = ranked_candidates[ranked_candidates["source_split"] == "test"]
    if "is_silver_parent" in test_ranking.columns:
        correct = test_ranking[test_ranking["is_silver_parent"]].copy()
    else:
        correct = test_ranking.merge(
            gold[["source_message_id", "silver_parent_message_id"]],
            left_on=["source_message_id", "target_message_id"],
            right_on=["source_message_id", "silver_parent_message_id"],
            how="inner",
            validate="many_to_one",
        )
    correct_by_source = correct.set_index("source_message_id") if not correct.empty else None
    rows: list[dict[str, Any]] = []
    for item in gold.itertuples(index=False):
        source_id = str(item.source_message_id)
        target_id = str(item.silver_parent_message_id)
        source = message_index.loc[source_id]
        target = message_index.loc[target_id]
        found = correct_by_source is not None and source_id in correct_by_source.index
        match = correct_by_source.loc[source_id] if found else None
        if isinstance(match, pd.DataFrame):
            match = match.iloc[0]
        rows.append(
            {
                "source_message_id": source_id,
                "silver_parent_message_id": target_id,
                "channel_key": source["channel_key"],
                "channel_name": source["channel_name"],
                "candidate_count": int(candidate_counts.get(source_id, 0)),
                "candidate_available": bool(found),
                "candidate_generation_rank": (
                    int(match["candidate_generation_rank"]) if found else None
                ),
                "rank_position": int(match["rank_position"]) if found else None,
                "message_distance": int(
                    source["message_position"] - target["message_position"]
                ),
                "time_gap_seconds": float(
                    (source["timestamp"] - target["timestamp"]).total_seconds()
                ),
                "hit_at_1": float(found and int(match["rank_position"]) <= 1),
                "hit_at_3": float(found and int(match["rank_position"]) <= 3),
                "hit_at_5": float(found and int(match["rank_position"]) <= 5),
                "hit_at_10": float(found and int(match["rank_position"]) <= 10),
                "reciprocal_rank": 1.0 / int(match["rank_position"]) if found else 0.0,
            }
        )
    return pd.DataFrame.from_records(rows)


def candidate_generation_metrics(
    outcomes: pd.DataFrame,
    *,
    ks: tuple[int, ...],
) -> dict[str, Any]:
    count = len(outcomes)
    curve: list[dict[str, Any]] = []
    for k in ks:
        available_at_k = outcomes["candidate_generation_rank"].fillna(float("inf")).le(k)
        truncated_counts = outcomes["candidate_count"].clip(upper=k)
        curve.append(
            {
                "k": int(k),
                "candidate_recall": float(available_at_k.mean()) if count else 0.0,
                "mean_candidate_count": float(truncated_counts.mean()) if count else 0.0,
                "median_candidate_count": float(truncated_counts.median()) if count else 0.0,
            }
        )
    return {
        "silver_reply_count": int(count),
        "candidate_recall": float(outcomes["candidate_available"].mean()) if count else 0.0,
        "candidate_recall_by_k": curve,
        "mean_candidate_count": float(outcomes["candidate_count"].mean()) if count else 0.0,
        "median_candidate_count": float(outcomes["candidate_count"].median()) if count else 0.0,
    }


def ranking_metrics(outcomes: pd.DataFrame) -> dict[str, Any]:
    available = outcomes[outcomes["candidate_available"]]
    overall = _ranking_summary(outcomes)
    conditional = _ranking_summary(available)
    conditional["evaluated_reply_count"] = int(len(available))
    overall["evaluated_reply_count"] = int(len(outcomes))
    return {"overall": overall, "conditional": conditional}


def _ranking_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "mrr": 0.0,
            "mean_rank": None,
            "median_rank": None,
        }
    ranks = frame["rank_position"].dropna().astype(float)
    return {
        "recall_at_1": float(frame["hit_at_1"].mean()),
        "recall_at_3": float(frame["hit_at_3"].mean()),
        "recall_at_5": float(frame["hit_at_5"].mean()),
        "recall_at_10": float(frame["hit_at_10"].mean()),
        "mrr": float(frame["reciprocal_rank"].mean()),
        "mean_rank": float(ranks.mean()) if not ranks.empty else None,
        "median_rank": float(ranks.median()) if not ranks.empty else None,
    }


def stratified_metrics(
    outcomes: pd.DataFrame,
    *,
    parent_boundaries: tuple[int, ...],
    time_boundaries: tuple[float, ...],
    competition_low_max: int,
    competition_high_min: int,
) -> dict[str, list[dict[str, Any]]]:
    work = outcomes.copy()
    work["parent_distance_stratum"] = work["message_distance"].map(
        lambda value: _distance_label(int(value), parent_boundaries)
    )
    work["time_gap_stratum"] = work["time_gap_seconds"].map(
        lambda value: _time_label(float(value), time_boundaries)
    )
    work["competition_stratum"] = work["candidate_count"].map(
        lambda value: (
            "low"
            if value <= competition_low_max
            else "high" if value >= competition_high_min else "medium"
        )
    )
    return {
        "parent_distance": _summarize_strata(work, "parent_distance_stratum"),
        "time_gap": _summarize_strata(work, "time_gap_stratum"),
        "candidate_competition": _summarize_strata(work, "competition_stratum"),
    }


def _summarize_strata(frame: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, group in frame.groupby(column, sort=False):
        rows.append(
            {
                "stratum": str(label),
                "reply_count": int(len(group)),
                "candidate_recall": float(group["candidate_available"].mean()),
                "recall_at_1_overall": float(group["hit_at_1"].mean()),
                "mrr_overall": float(group["reciprocal_rank"].mean()),
            }
        )
    return rows


def _distance_label(value: int, boundaries: tuple[int, ...]) -> str:
    low = 1
    for boundary in boundaries:
        if value <= boundary:
            return f"{low}-{boundary}"
        low = boundary + 1
    return f">{boundaries[-1]}"


def _time_label(value: float, boundaries: tuple[float, ...]) -> str:
    previous = 0.0
    for boundary in boundaries:
        if value < boundary:
            return (
                f"<{_duration_label(boundary)}"
                if previous == 0.0
                else f"{_duration_label(previous)}-{_duration_label(boundary)}"
            )
        previous = boundary
    return f">={_duration_label(boundaries[-1])}"


def _duration_label(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:g}s"
    minutes = seconds / 60.0
    return f"{minutes:g}min"
