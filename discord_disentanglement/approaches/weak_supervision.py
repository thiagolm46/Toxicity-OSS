from __future__ import annotations

import numpy as np
import pandas as pd

from .base import (
    ApproachContractError,
    ApproachFitData,
    ApproachReference,
    ApproachScore,
    DisentanglementApproach,
    PREDICTION_FEATURE_COLUMNS,
    feature_matrix,
)
from .math_utils import LogisticModel, fit_logistic_regression


class WeakSupervisionPairwiseRankerApproach(DisentanglementApproach):
    """Pairwise ranker trained only on train-split explicit reply positives."""

    approach_id = "weak_supervision"
    display_name = "Weak supervision direct-reply pairwise ranker (pilot proxy)"
    uses_direct_reply_training = True
    uses_discord_labels = True
    implementation_type = "PILOT_PROXY"
    training_source = "discord_direct_reply_train_only"
    adaptations = (
        "Ranker logistico pairwise local; nao usa Sentence-BERT na implementacao atual.",
    )
    link_threshold = 0.55
    references = (
        ApproachReference(
            citation=(
                "Reimers, Nils; Gurevych, Iryna (2019). Sentence-BERT: Sentence "
                "Embeddings using Siamese BERT-Networks. EMNLP-IJCNLP 2019."
            ),
            doi="10.18653/v1/D19-1410",
            url="https://aclanthology.org/D19-1410/",
        ),
        ApproachReference(
            citation="SentenceTransformers CrossEncoder training overview.",
            url="https://www.sbert.net/docs/cross_encoder/training_overview.html",
        ),
    )

    def __init__(self, *, negatives_per_positive: int = 6) -> None:
        super().__init__()
        self.negatives_per_positive = negatives_per_positive
        self._model: LogisticModel | None = None

    @property
    def requires_training(self) -> bool:
        return True

    def fit(self, data: ApproachFitData) -> None:
        if data.train_gold.empty:
            raise ApproachContractError(
                "weak_supervision requer ao menos um direct_reply valido no split de treino; "
                "nenhuma outra abordagem sera usada como fallback"
            )
        candidate_matrix = feature_matrix(data.train_candidates)
        gold_by_source = dict(
            zip(
                data.train_gold["source_message_id"].astype(str),
                data.train_gold["target_message_id"].astype(str),
                strict=False,
            )
        )
        target_values = data.train_candidates["target_message_id"].astype(str).to_numpy()

        pair_differences: list[np.ndarray] = []
        sources_with_gold_candidate = 0
        for source_id, positions in data.train_candidates.groupby(
            "source_message_id", sort=False
        ).indices.items():
            gold_target = gold_by_source.get(str(source_id))
            if gold_target is None:
                continue
            group_positions = np.asarray(positions, dtype=np.int64)
            positive_positions = group_positions[target_values[group_positions] == gold_target]
            if positive_positions.size == 0:
                continue
            negative_positions = group_positions[target_values[group_positions] != gold_target]
            if negative_positions.size == 0:
                continue
            sources_with_gold_candidate += 1
            # The common candidate order deterministically interleaves recency
            # and topical strength; no reply label participates in that order.
            selected_negatives = negative_positions[: self.negatives_per_positive]
            positive = candidate_matrix[int(positive_positions[0])]
            for negative_position in selected_negatives:
                difference = positive - candidate_matrix[int(negative_position)]
                pair_differences.append(difference)

        if not pair_differences:
            raise ApproachContractError(
                "direct_reply de treino nao apareceu no universo comum de candidatos com "
                "ao menos um negativo; aumente a janela comum, sem fallback de abordagem"
            )
        positive_differences = np.vstack(pair_differences)
        training_x = np.vstack([positive_differences, -positive_differences])
        training_y = np.concatenate(
            [
                np.ones(len(positive_differences), dtype=np.float64),
                np.zeros(len(positive_differences), dtype=np.float64),
            ]
        )
        self._model = fit_logistic_regression(
            training_x,
            training_y,
            epochs=220,
            learning_rate=0.10,
            l2_penalty=1e-3,
        )
        self.fit_diagnostics = {
            "training_mode": "pairwise_logistic_ranker",
            "weak_label": "direct_reply_train_only",
            "direct_reply_labels_available_train": int(len(data.train_gold)),
            "direct_reply_sources_with_common_candidate": sources_with_gold_candidate,
            "paired_positive_negative_differences": int(len(positive_differences)),
            "negatives_per_positive_cap": self.negatives_per_positive,
            "features": list(PREDICTION_FEATURE_COLUMNS),
            "validation_labels_used": 0,
            "external_model_downloads": False,
        }

    def method_hyperparameters(self) -> dict[str, object]:
        return {
            "negatives_per_positive": self.negatives_per_positive,
            "pairwise_logistic_epochs": 220,
            "pairwise_logistic_learning_rate": 0.10,
            "pairwise_logistic_l2": 1e-3,
            "features": list(PREDICTION_FEATURE_COLUMNS),
            "score_interpretation": (
                "monotonic_pairwise_utility; link abstention is calibrated by a "
                "label-free validation quantile, not as a calibrated class probability"
            ),
        }

    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        if self._model is None:
            raise ApproachContractError("weak_supervision.score chamado antes de fit")
        scores = self._model.predict_proba(feature_matrix(candidates))
        return ApproachScore(
            scores=np.asarray(scores, dtype=np.float64),
            diagnostics={"scoring_rule": "manual_pairwise_logistic_utility"},
        )


if __name__ == "__main__":
    raise SystemExit(
        "Execute pelo runner comum: python -m discord_disentanglement.experiments "
        "run --approach weak_supervision --input <arquivo> --output <diretorio>"
    )
