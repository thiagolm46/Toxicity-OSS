"""Reconstrução e avaliação projetada das threads silver de replies explícitos."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def silver_projection(
    *,
    messages: pd.DataFrame,
    direct_reply_gold: pd.DataFrame,
    message_assignments: pd.DataFrame,
) -> pd.DataFrame:
    """Project predicted clusters onto explicit-reply components touching test sources."""
    graph = _UnionFind()
    test_sources = set(
        direct_reply_gold.loc[
            direct_reply_gold["source_split"] == "test", "source_message_id"
        ].astype(str)
    )
    for edge in direct_reply_gold.itertuples(index=False):
        graph.union(str(edge.source_message_id), str(edge.target_message_id))
    selected_roots = {graph.find(source_id) for source_id in test_sources}
    evaluable = {
        message_id
        for message_id in graph.parent
        if graph.find(message_id) in selected_roots
    }
    if not evaluable:
        return pd.DataFrame(
            columns=[
                "message_id",
                "channel_key",
                "silver_thread_id",
                "predicted_thread_id",
            ]
        )
    message_meta = messages.set_index("message_id")[["channel_key", "channel_name"]]
    predictions = message_assignments.set_index("message_id")["predicted_thread_id"]
    rows = []
    for message_id in sorted(evaluable):
        rows.append(
            {
                "message_id": message_id,
                "channel_key": message_meta.loc[message_id, "channel_key"],
                "channel_name": message_meta.loc[message_id, "channel_name"],
                "silver_thread_id": f"SILVER_{graph.find(message_id)}",
                "predicted_thread_id": str(predictions.loc[message_id]),
            }
        )
    return pd.DataFrame.from_records(rows)


def projected_conversation_metrics(projection: pd.DataFrame) -> dict[str, Any]:
    if projection.empty:
        return {
            "status": "not_available",
            "evaluable_message_count": 0,
            "silver_thread_count": 0,
            "predicted_projected_thread_count": 0,
            "ari": None,
            "nmi": None,
            "variation_of_information": None,
            "bcubed_precision": None,
            "bcubed_recall": None,
            "bcubed_f1": None,
            "exact_match": None,
            "fragmentation_rate": None,
            "merge_rate": None,
        }
    silver = _labels_with_bootstrap_replica(projection, "silver_thread_id")
    predicted = _labels_with_bootstrap_replica(projection, "predicted_thread_id")
    precision, recall, f1 = _bcubed(silver, predicted)
    return {
        "status": "partial_silver_projection",
        "projection_rule": (
            "Predicted clusters are intersected with messages belonging to explicit-reply "
            "components that touch at least one held-out test source. Unobserved messages "
            "are not treated as negatives."
        ),
        "evaluable_message_count": int(len(projection)),
        "silver_thread_count": int(pd.Series(silver).nunique()),
        "predicted_projected_thread_count": int(pd.Series(predicted).nunique()),
        "ari": float(adjusted_rand_score(silver, predicted)),
        "nmi": float(normalized_mutual_info_score(silver, predicted)),
        "variation_of_information": float(_variation_of_information(silver, predicted)),
        "bcubed_precision": precision,
        "bcubed_recall": recall,
        "bcubed_f1": f1,
        "exact_match": float(_exact_match_rate(silver, predicted)),
        "fragmentation_rate": float(_fragmentation_rate(silver, predicted)),
        "merge_rate": float(_merge_rate(silver, predicted)),
    }


def _labels_with_bootstrap_replica(frame: pd.DataFrame, column: str) -> list[str]:
    if "_bootstrap_replica" not in frame.columns:
        return frame[column].astype(str).tolist()
    return (
        frame["_bootstrap_replica"].astype(str)
        + ":"
        + frame[column].astype(str)
    ).tolist()


def _bcubed(silver: list[str], predicted: list[str]) -> tuple[float, float, float]:
    silver_groups: defaultdict[str, set[int]] = defaultdict(set)
    predicted_groups: defaultdict[str, set[int]] = defaultdict(set)
    for position, (silver_label, predicted_label) in enumerate(zip(silver, predicted, strict=True)):
        silver_groups[silver_label].add(position)
        predicted_groups[predicted_label].add(position)
    precisions: list[float] = []
    recalls: list[float] = []
    for position, (silver_label, predicted_label) in enumerate(zip(silver, predicted, strict=True)):
        overlap = len(silver_groups[silver_label] & predicted_groups[predicted_label])
        precisions.append(overlap / len(predicted_groups[predicted_label]))
        recalls.append(overlap / len(silver_groups[silver_label]))
    precision = float(np.mean(precisions))
    recall = float(np.mean(recalls))
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _variation_of_information(silver: list[str], predicted: list[str]) -> float:
    count = len(silver)
    silver_counts = Counter(silver)
    predicted_counts = Counter(predicted)
    joint = Counter(zip(silver, predicted, strict=True))

    def entropy(counts: Counter[Any]) -> float:
        return -sum(
            (value / count) * math.log(value / count)
            for value in counts.values()
            if value
        )

    mutual_information = 0.0
    for (silver_label, predicted_label), value in joint.items():
        probability = value / count
        mutual_information += probability * math.log(
            probability
            / ((silver_counts[silver_label] / count) * (predicted_counts[predicted_label] / count))
        )
    return entropy(silver_counts) + entropy(predicted_counts) - 2.0 * mutual_information


def _cluster_members(labels: list[str]) -> dict[str, frozenset[int]]:
    groups: defaultdict[str, set[int]] = defaultdict(set)
    for position, label in enumerate(labels):
        groups[label].add(position)
    return {label: frozenset(members) for label, members in groups.items()}


def _exact_match_rate(silver: list[str], predicted: list[str]) -> float:
    silver_sets = list(_cluster_members(silver).values())
    predicted_sets = set(_cluster_members(predicted).values())
    return sum(group in predicted_sets for group in silver_sets) / len(silver_sets)


def _fragmentation_rate(silver: list[str], predicted: list[str]) -> float:
    predicted_by_position = dict(enumerate(predicted))
    silver_sets = _cluster_members(silver).values()
    return sum(
        len({predicted_by_position[position] for position in members}) > 1
        for members in silver_sets
    ) / len(list(_cluster_members(silver).values()))


def _merge_rate(silver: list[str], predicted: list[str]) -> float:
    silver_by_position = dict(enumerate(silver))
    predicted_sets = _cluster_members(predicted).values()
    return sum(
        len({silver_by_position[position] for position in members}) > 1
        for members in predicted_sets
    ) / len(list(_cluster_members(predicted).values()))
