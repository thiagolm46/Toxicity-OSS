from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd


class ApproachContractError(RuntimeError):
    """Raised when an approach cannot satisfy its declared experimental contract."""


@dataclass(frozen=True, slots=True)
class ApproachReference:
    citation: str
    url: str
    doi: str | None = None
    code_url: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "citation": self.citation,
            "url": self.url,
            "doi": self.doi,
            "code_url": self.code_url,
        }


@dataclass(slots=True)
class ApproachFitData:
    """Inputs made available during fitting.

    Candidate frames deliberately contain no explicit-reply label or native thread
    identifier.  ``train_gold`` is a separate two-column frame and is populated only
    for approaches that explicitly declare supervised use of direct replies.
    """

    train_candidates: pd.DataFrame
    validation_candidates: pd.DataFrame
    train_gold: pd.DataFrame
    random_seed: int


@dataclass(slots=True)
class ApproachScore:
    scores: np.ndarray
    diagnostics: dict[str, Any] = field(default_factory=dict)


class DisentanglementApproach(ABC):
    """Common interface for held-out message-to-parent ranking approaches."""

    approach_id: ClassVar[str]
    display_name: ClassVar[str]
    fidelity: ClassVar[str] = "pilot_proxy"
    implementation_type: ClassVar[str] = "PILOT_PROXY"
    uses_direct_reply_training: ClassVar[bool] = False
    uses_discord_labels: ClassVar[bool] = False
    training_source: ClassVar[str] = "none"
    paper_title: ClassVar[str | None] = None
    paper_authors: ClassVar[str | None] = None
    paper_year: ClassVar[int | None] = None
    venue: ClassVar[str | None] = None
    source_repository: ClassVar[str | None] = None
    source_commit: ClassVar[str | None] = None
    checkpoint: ClassVar[str | None] = None
    adaptations: ClassVar[tuple[str, ...]] = ()
    requires_checkpoint: ClassVar[bool] = False
    references: ClassVar[tuple[ApproachReference, ...]] = ()
    link_threshold: ClassVar[float] = 0.50

    def __init__(self) -> None:
        self.fit_diagnostics: dict[str, Any] = {}
        self.effective_link_threshold: float | None = None
        self.threshold_diagnostics: dict[str, Any] = {}

    @abstractmethod
    def fit(self, data: ApproachFitData) -> None:
        """Fit using the chronologically earliest 60% only."""

    @abstractmethod
    def score(self, candidates: pd.DataFrame) -> ApproachScore:
        """Score a label-free candidate frame without mutating it."""

    def manifest_metadata(self) -> dict[str, Any]:
        return {
            "approach_id": self.approach_id,
            "display_name": self.display_name,
            "fidelity": self.fidelity,
            "implementation_type": self.implementation_type,
            "claim": self._scientific_claim(),
            "uses_direct_reply_training": self.uses_direct_reply_training,
            "scientific_metadata": {
                "paper_title": self.paper_title,
                "paper_authors": self.paper_authors,
                "paper_year": self.paper_year,
                "venue": self.venue,
                "source_repository": self.source_repository,
                "source_commit": self.source_commit,
                "checkpoint": self.checkpoint,
                "adaptations": list(self.adaptations),
                "training_source": self.training_source,
                "uses_discord_labels": self.uses_discord_labels,
                "uses_direct_reply_train": self.uses_direct_reply_training,
                "uses_direct_reply_test": "evaluation_only",
            },
            "capabilities": {
                "requires_training": self.requires_training,
                "requires_checkpoint": self.requires_checkpoint,
                "produces_rankings": True,
                "produces_links": True,
                "produces_threads": True,
                "supports_scores": True,
            },
            "default_link_threshold": self.link_threshold,
            "effective_link_threshold": self.effective_link_threshold,
            "threshold_calibration": self.threshold_diagnostics,
            "method_hyperparameters": self.method_hyperparameters(),
            "references": [reference.as_dict() for reference in self.references],
            "fit_diagnostics": self.fit_diagnostics,
        }

    def method_hyperparameters(self) -> dict[str, Any]:
        return {}

    def preflight(self) -> None:
        """Validate optional resources before any run artifacts are written."""

    def _scientific_claim(self) -> str:
        if self.implementation_type == "PILOT_PROXY":
            return (
                "Proxy exploratorio de piloto; nao constitui reproducao fiel nem "
                "reimplementacao oficial do artigo relacionado."
            )
        if self.implementation_type == "INSPIRED_BY":
            return (
                "Implementacao inspirada no mecanismo cientifico descrito; nao e "
                "reproducao, reimplementacao fiel nem codigo oficial do artigo."
            )
        return f"Implementacao classificada como {self.implementation_type}."

    @property
    def requires_training(self) -> bool:
        return False


PREDICTION_FEATURE_COLUMNS: tuple[str, ...] = (
    "temporal_proximity",
    "semantic_similarity",
    "lexical_overlap",
    "source_mentions_target",
    "target_mentions_source",
    "adjacent_message",
    "author_turn",
    "same_author",
    "question_answer",
    "technical_overlap",
    "length_similarity",
    "recency_rank_score",
)

FORBIDDEN_PREDICTION_COLUMNS: frozenset[str] = frozenset(
    {
        "reply_to_message_id",
        "reply_to",
        "reply_target_id",
        "reference_id",
        "reference",
        "referenced_message_id",
        "message_reference",
        "referenced_message",
        "explicit_reply",
        "direct_reply",
        "label",
        "gold_target_message_id",
        "silver_parent_message_id",
        "is_silver_parent",
        "candidate_available",
        "native_thread_id",
        "thread_id",
    }
)


def validate_prediction_frame(candidates: pd.DataFrame) -> None:
    leaked = FORBIDDEN_PREDICTION_COLUMNS.intersection(candidates.columns)
    if leaked:
        raise ApproachContractError(
            "Colunas de gold/metadados proibidas chegaram a uma abordagem: "
            + ", ".join(sorted(leaked))
        )
    missing = set(PREDICTION_FEATURE_COLUMNS).difference(candidates.columns)
    if missing:
        raise ApproachContractError(
            "Features comuns ausentes: " + ", ".join(sorted(missing))
        )


def feature_matrix(
    candidates: pd.DataFrame,
    columns: tuple[str, ...] = PREDICTION_FEATURE_COLUMNS,
) -> np.ndarray:
    validate_prediction_frame(candidates)
    if candidates.empty:
        return np.empty((0, len(columns)), dtype=np.float64)
    return (
        candidates.loc[:, list(columns)]
        .fillna(0.0)
        .astype("float64")
        .to_numpy(copy=True)
    )
