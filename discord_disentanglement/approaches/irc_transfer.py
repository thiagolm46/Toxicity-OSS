"""Adapter para transferência supervisionada IRC -> Discord."""

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
    / "irc_transfer.kummerfeld2019.v1.json"
)


class IrcTransferAdapter(DisentanglementApproach):
    approach_id = "irc_transfer"
    display_name = "Supervised Ubuntu IRC to Discord transfer"
    fidelity = "inspired_by"
    implementation_type = "INSPIRED_BY"
    requires_checkpoint = True
    training_source = "kummerfeld_ubuntu_irc_annotated_train"
    paper_title = "A Large-Scale Corpus for Conversation Disentanglement"
    paper_authors = "Jonathan K. Kummerfeld et al."
    paper_year = 2019
    venue = "ACL 2019"
    source_repository = "https://github.com/jkkummerfeld/irc-disentanglement"
    source_commit = "82ed04f9627a45d0d6f2ec3c8683c88eb408a0d5"
    checkpoint = "configs/approaches/irc_transfer.kummerfeld2019.v1.json"
    adaptations = (
        "Modelo DyNet oficial auditado, mas sem checkpoint distribuido e incompatível com Python 3.12.",
        "Ranker pairwise reimplementado com features comuns para permitir transferencia controlada.",
        "Treino usa somente annotations IRC; nenhum direct_reply Discord entra em fit ou inferencia.",
        "Tokenizacao e sinais de mencao foram adaptados do formato IRC ao contrato comum.",
    )
    references = (
        ApproachReference(
            citation=(
                "Kummerfeld, Jonathan K. et al. (2019). A Large-Scale Corpus for "
                "Conversation Disentanglement. ACL 2019."
            ),
            doi="10.18653/v1/P19-1374",
            url="https://aclanthology.org/P19-1374/",
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
        self.fit_diagnostics = {
            "training_mode": "external_supervised_irc_checkpoint_no_discord_fit",
            "direct_reply_labels_used": 0,
            "discord_candidates_observed_for_fit": 0,
            "checkpoint_sha256": self._checkpoint.sha256,
            "external_training": self._checkpoint.payload.get("training", {}),
        }

    def preflight(self) -> None:
        load_external_checkpoint(
            self.checkpoint_path, expected_approach_id=self.approach_id
        )

    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        if self._checkpoint is None:
            raise RuntimeError("irc_transfer.score chamado antes de fit")
        scores = self._checkpoint.model.predict_proba(feature_matrix(candidates))
        return ApproachScore(
            scores=np.asarray(scores, dtype=np.float64),
            diagnostics={
                "scoring_rule": "external_irc_supervised_pairwise_checkpoint",
                "checkpoint_sha256": self._checkpoint.sha256,
            },
        )

    def method_hyperparameters(self) -> dict[str, object]:
        return {
            "checkpoint_path": str(self.checkpoint_path),
            "score_interpretation": "cross-domain pairwise utility; not calibrated probability",
        }
