from __future__ import annotations

import numpy as np
import pandas as pd

from .base import (
    ApproachContractError,
    ApproachFitData,
    ApproachReference,
    ApproachScore,
    DisentanglementApproach,
    feature_matrix,
)
from .math_utils import (
    LogisticModel,
    deterministic_subsample_indices,
    fit_logistic_regression,
)


CONVERSATION_VIEW: tuple[str, ...] = (
    "temporal_proximity",
    "source_mentions_target",
    "target_mentions_source",
    "adjacent_message",
    "author_turn",
    "same_author",
    "question_answer",
    "recency_rank_score",
)

TOPIC_VIEW: tuple[str, ...] = (
    "semantic_similarity",
    "lexical_overlap",
    "technical_overlap",
    "length_similarity",
)


class UnsupervisedCoTrainingApproach(DisentanglementApproach):
    """Two-view pseudo-label exchange without direct-reply supervision."""

    approach_id = "co_training"
    display_name = "Unsupervised two-view co-training (pilot proxy)"
    link_threshold = 0.58
    references = (
        ApproachReference(
            citation=(
                "Liu, Hui; Shi, Zhan; Zhu, Xiaodan (2021). Unsupervised Conversation "
                "Disentanglement through Co-Training. EMNLP 2021."
            ),
            doi="10.18653/v1/2021.emnlp-main.181",
            url="https://aclanthology.org/2021.emnlp-main.181/",
            code_url="https://github.com/LayneIns/Unsupervised_dialo_disentanglement",
        ),
    )

    def __init__(self, *, maximum_fit_candidates: int = 120_000, rounds: int = 3) -> None:
        super().__init__()
        self.maximum_fit_candidates = maximum_fit_candidates
        self.rounds = rounds
        self._conversation_model: LogisticModel | None = None
        self._topic_model: LogisticModel | None = None

    def fit(self, data: ApproachFitData) -> None:
        if data.train_candidates.empty:
            raise ApproachContractError("co_training requer candidatos no split de treino")
        indices = deterministic_subsample_indices(
            len(data.train_candidates), self.maximum_fit_candidates
        )
        sampled = data.train_candidates.iloc[indices].reset_index(drop=True)
        conversation_x = feature_matrix(sampled, CONVERSATION_VIEW)
        topic_x = feature_matrix(sampled, TOPIC_VIEW)

        conversation_anchor = (
            0.34 * sampled["temporal_proximity"].to_numpy(dtype=float)
            + 0.22 * sampled["adjacent_message"].to_numpy(dtype=float)
            + 0.18 * sampled["source_mentions_target"].to_numpy(dtype=float)
            + 0.14 * sampled["question_answer"].to_numpy(dtype=float)
            + 0.12 * sampled["author_turn"].to_numpy(dtype=float)
        )
        topic_anchor = (
            0.55 * sampled["semantic_similarity"].to_numpy(dtype=float)
            + 0.25 * sampled["lexical_overlap"].to_numpy(dtype=float)
            + 0.12 * sampled["technical_overlap"].to_numpy(dtype=float)
            + 0.08 * sampled["length_similarity"].to_numpy(dtype=float)
        )
        conversation_labels = _quantile_seed_labels(conversation_anchor)
        topic_labels = _quantile_seed_labels(topic_anchor)

        round_summaries: list[dict[str, int]] = []
        for round_index in range(self.rounds):
            self._conversation_model = _fit_on_labeled(
                conversation_x, conversation_labels
            )
            self._topic_model = _fit_on_labeled(topic_x, topic_labels)
            conversation_probability = self._conversation_model.predict_proba(conversation_x)
            topic_probability = self._topic_model.predict_proba(topic_x)

            new_conversation_labels = _teach_unlabeled(
                conversation_labels, topic_probability
            )
            new_topic_labels = _teach_unlabeled(
                topic_labels, conversation_probability
            )
            round_summaries.append(
                {
                    "round": round_index + 1,
                    "conversation_labeled": int((new_conversation_labels >= 0).sum()),
                    "topic_labeled": int((new_topic_labels >= 0).sum()),
                }
            )
            conversation_labels = new_conversation_labels
            topic_labels = new_topic_labels

        # Refit once on the labels produced in the last exchange.
        self._conversation_model = _fit_on_labeled(conversation_x, conversation_labels)
        self._topic_model = _fit_on_labeled(topic_x, topic_labels)
        self.fit_diagnostics = {
            "training_mode": "unsupervised_two_view_pseudo_label_exchange",
            "direct_reply_labels_used": 0,
            "train_candidates_available": int(len(data.train_candidates)),
            "train_candidates_sampled": int(len(sampled)),
            "conversation_view": list(CONVERSATION_VIEW),
            "topic_view": list(TOPIC_VIEW),
            "rounds": round_summaries,
            "validation_labels_used": 0,
            "external_model_downloads": False,
        }

    def method_hyperparameters(self) -> dict[str, object]:
        return {
            "maximum_fit_candidates": self.maximum_fit_candidates,
            "co_training_rounds": self.rounds,
            "seed_low_quantile": 0.20,
            "seed_high_quantile": 0.80,
            "teacher_negative_probability": 0.18,
            "teacher_positive_probability": 0.82,
            "logistic_epochs_per_round": 100,
            "conversation_view": list(CONVERSATION_VIEW),
            "topic_view": list(TOPIC_VIEW),
        }

    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        if self._conversation_model is None or self._topic_model is None:
            raise ApproachContractError("co_training.score chamado antes de fit")
        conversation_probability = self._conversation_model.predict_proba(
            feature_matrix(candidates, CONVERSATION_VIEW)
        )
        topic_probability = self._topic_model.predict_proba(
            feature_matrix(candidates, TOPIC_VIEW)
        )
        # Geometric agreement penalizes candidates supported by only one view.
        scores = np.sqrt(conversation_probability * topic_probability)
        return ApproachScore(
            scores=np.asarray(scores, dtype=np.float64),
            diagnostics={
                "scoring_rule": "geometric_mean_of_conversation_and_topic_views"
            },
        )


def _quantile_seed_labels(values: np.ndarray) -> np.ndarray:
    labels = np.full(len(values), -1, dtype=np.int8)
    if len(values) < 2:
        raise ApproachContractError("co_training requer ao menos dois candidatos de treino")
    low = float(np.quantile(values, 0.20))
    high = float(np.quantile(values, 0.80))
    labels[values <= low] = 0
    labels[values >= high] = 1
    if not np.any(labels == 0) or not np.any(labels == 1):
        order = np.argsort(values, kind="stable")
        labels[order[: max(1, len(order) // 5)]] = 0
        labels[order[-max(1, len(order) // 5) :]] = 1
    return labels


def _teach_unlabeled(labels: np.ndarray, teacher_probability: np.ndarray) -> np.ndarray:
    updated = labels.copy()
    unlabeled = updated < 0
    updated[unlabeled & (teacher_probability <= 0.18)] = 0
    updated[unlabeled & (teacher_probability >= 0.82)] = 1
    return updated


def _fit_on_labeled(features: np.ndarray, labels: np.ndarray) -> LogisticModel:
    mask = labels >= 0
    selected_y = labels[mask].astype(np.float64)
    if set(np.unique(selected_y).tolist()) != {0.0, 1.0}:
        raise ApproachContractError("uma view do co_training perdeu uma das classes pseudo-rotuladas")
    return fit_logistic_regression(
        features[mask],
        selected_y,
        epochs=100,
        learning_rate=0.10,
        l2_penalty=2e-3,
    )


if __name__ == "__main__":
    raise SystemExit(
        "Execute pelo runner comum: python -m discord_disentanglement.experiments "
        "run --approach co_training --input <arquivo> --output <diretorio>"
    )
