"""Adapter Chi-inspired para checkpoint auto-supervisionado externo."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .base import ApproachFitData, ApproachReference, ApproachScore, DisentanglementApproach, feature_matrix
from .external_checkpoint import ExternalCheckpoint, load_external_checkpoint


DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "approaches"
    / "chi_zero_shot.irc_self_supervised.v1.json"
)


class ChiZeroShotAdapter(DisentanglementApproach):
    approach_id = "chi_zero_shot"
    display_name = "Chi-inspired self-supervised response selection"
    fidelity = "inspired_by"
    implementation_type = "INSPIRED_BY"
    requires_checkpoint = True
    training_source = "external_unlabeled_ubuntu_irc_response_selection"
    paper_title = "Zero-Shot Dialogue Disentanglement by Self-Supervised Entangled Response Selection"
    paper_authors = "Ta-Chung Chi; Alexander I. Rudnicky"
    paper_year = 2021
    venue = "EMNLP 2021"
    source_repository = "https://github.com/chijames/zero_shot_dialogue_disentanglement"
    source_commit = "ad0ef53ff192fae682ce6b3826619df936e89d9a"
    checkpoint = "configs/approaches/chi_zero_shot.irc_self_supervised.v1.json"
    adaptations = (
        "Codigo oficial auditado, mas nao incorporado por ausencia de licenca e checkpoint publicado.",
        "Encoder BERT hierarquico substituido por atencao linear auditavel sobre features comuns.",
        "Treino externo usa contextos IRC corretos versus respostas deslocadas, sem reply labels.",
        "Inferencia usa score individual como proxy da atencao e nunca usa direct_reply Discord.",
    )
    references = (
        ApproachReference(
            citation=(
                "Chi, Ta-Chung; Rudnicky, Alexander I. (2021). Zero-Shot Dialogue "
                "Disentanglement by Self-Supervised Entangled Response Selection. EMNLP 2021."
            ),
            doi="10.18653/v1/2021.emnlp-main.400",
            url="https://aclanthology.org/2021.emnlp-main.400/",
            code_url=source_repository,
        ),
    )

    def __init__(self, checkpoint_path: str | Path | None = None) -> None:
        super().__init__()
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else DEFAULT_CHECKPOINT
        self._checkpoint: ExternalCheckpoint | None = None

    def fit(self, data: ApproachFitData) -> None:
        self._checkpoint = load_external_checkpoint(
            self.checkpoint_path, expected_approach_id=self.approach_id
        )
        training = self._checkpoint.payload.get("training", {})
        self.fit_diagnostics = {
            "training_mode": "external_self_supervised_checkpoint_no_discord_fit",
            "direct_reply_labels_used": 0,
            "discord_candidates_observed_for_fit": 0,
            "checkpoint_sha256": self._checkpoint.sha256,
            "external_training": training,
        }

    def preflight(self) -> None:
        load_external_checkpoint(
            self.checkpoint_path, expected_approach_id=self.approach_id
        )

    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        if self._checkpoint is None:
            raise RuntimeError("chi_zero_shot.score chamado antes de fit")
        scores = self._checkpoint.model.predict_proba(feature_matrix(candidates))
        return ApproachScore(
            scores=np.asarray(scores, dtype=np.float64),
            diagnostics={
                "scoring_rule": "external_self_supervised_linear_attention_checkpoint",
                "checkpoint_sha256": self._checkpoint.sha256,
            },
        )

    def method_hyperparameters(self) -> dict[str, object]:
        return {
            "checkpoint_path": str(self.checkpoint_path),
            "score_interpretation": "attention proxy; not calibrated link probability",
        }
