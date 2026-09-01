from __future__ import annotations

import numpy as np
import pandas as pd

from .base import (
    ApproachFitData,
    ApproachReference,
    ApproachScore,
    DisentanglementApproach,
    feature_matrix,
)
from .math_utils import sigmoid


class ZeroShotResponseSelectionApproach(DisentanglementApproach):
    """Label-free response selection using frozen conversational priors.

    The paper uses a neural self-supervised response selector.  This offline pilot
    keeps only the zero-shot response-selection idea and replaces the neural model
    with fixed, documented TF-IDF/discourse priors.
    """

    approach_id = "zero_shot"
    display_name = "Zero-shot response selection (pilot proxy)"
    link_threshold = 0.61
    implementation_type = "PILOT_PROXY"
    training_source = "none_frozen_internal_priors"
    paper_title = "Zero-Shot Dialogue Disentanglement by Self-Supervised Entangled Response Selection"
    paper_authors = "Ta-Chung Chi; Alexander I. Rudnicky"
    paper_year = 2021
    venue = "EMNLP 2021"
    source_repository = "https://github.com/chijames/zero_shot_dialogue_disentanglement"
    adaptations = (
        "Baseline heuristico interno; nao utiliza o modelo ou checkpoint do artigo.",
    )
    references = (
        ApproachReference(
            citation=(
                "Chi, Ta-Chung; Rudnicky, Alexander I. (2021). Zero-Shot Dialogue "
                "Disentanglement by Self-Supervised Entangled Response Selection. EMNLP 2021."
            ),
            doi="10.18653/v1/2021.emnlp-main.400",
            url="https://aclanthology.org/2021.emnlp-main.400/",
            code_url="https://github.com/chijames/zero_shot_dialogue_disentanglement",
        ),
    )

    _weights = np.asarray(
        [
            1.30,  # temporal_proximity
            1.75,  # semantic_similarity
            0.65,  # lexical_overlap
            1.20,  # source_mentions_target
            0.20,  # target_mentions_source
            0.75,  # adjacent_message
            0.35,  # author_turn
            -0.45,  # same_author
            0.75,  # question_answer
            0.30,  # technical_overlap
            0.20,  # length_similarity
            0.35,  # recency_rank_score
        ],
        dtype=np.float64,
    )

    def fit(self, data: ApproachFitData) -> None:
        # Deliberately no fitting: the coefficients are frozen before the test split.
        self.fit_diagnostics = {
            "training_mode": "none_frozen_priors",
            "direct_reply_labels_used": 0,
            "train_candidate_count_observed": int(len(data.train_candidates)),
            "validation_labels_used": 0,
            "external_model_downloads": False,
        }

    def method_hyperparameters(self) -> dict[str, object]:
        return {
            "feature_weights_in_common_column_order": self._weights.tolist(),
            "logit_bias": -2.55,
            "weights_frozen_before_evaluation": True,
        }

    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        matrix = feature_matrix(candidates)
        scores = sigmoid(matrix @ self._weights - 2.55)
        return ApproachScore(
            scores=np.asarray(scores, dtype=np.float64),
            diagnostics={"scoring_rule": "frozen_weighted_tfidf_and_discourse_priors"},
        )


if __name__ == "__main__":
    raise SystemExit(
        "Execute pelo runner comum: python -m discord_disentanglement.experiments "
        "run --approach zero_shot --input <arquivo> --output <diretorio>"
    )
