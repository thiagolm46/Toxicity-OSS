from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


NEO4J_GUILD_ID = "787399249741479977"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    input_path: Path
    output_dir: Path
    guild_id: str = NEO4J_GUILD_ID
    guild_name: str | None = None
    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    test_fraction: float = 0.20
    max_previous_messages: int = 50
    max_candidates_per_message: int = 20
    max_time_delta_hours: float = 24.0
    random_seed: int = 42
    review_sample_size: int = 100
    validation_abstention_quantile: float = 0.25
    candidate_recall_ks: tuple[int, ...] = (5, 10, 20)
    parent_distance_boundaries: tuple[int, ...] = (2, 5, 10, 20)
    time_gap_boundaries_seconds: tuple[float, ...] = (30.0, 120.0, 300.0, 900.0)
    competition_low_max: int = 5
    competition_high_min: int = 15
    bootstrap_resamples: int = 1000
    bootstrap_confidence: float = 0.95
    bootstrap_unit: str = "channel"
    approach_settings: dict[str, dict[str, Any]] | None = None
    overwrite: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_path", Path(self.input_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        fractions = self.train_fraction + self.validation_fraction + self.test_fraction
        if abs(fractions - 1.0) > 1e-9:
            raise ValueError("train/validation/test devem somar 1.0")
        if any(
            abs(actual - required) > 1e-9
            for actual, required in zip(
                (self.train_fraction, self.validation_fraction, self.test_fraction),
                (0.60, 0.20, 0.20),
                strict=True,
            )
        ):
            raise ValueError("O protocolo comparavel fixa o split temporal em 60/20/20")
        if min(self.train_fraction, self.validation_fraction, self.test_fraction) <= 0:
            raise ValueError("todos os splits temporais devem ser positivos")
        if self.max_previous_messages < 1:
            raise ValueError("max_previous_messages deve ser >= 1")
        if not 1 <= self.max_candidates_per_message <= self.max_previous_messages:
            raise ValueError(
                "max_candidates_per_message deve estar entre 1 e max_previous_messages"
            )
        if self.max_time_delta_hours <= 0:
            raise ValueError("max_time_delta_hours deve ser positivo")
        if self.review_sample_size < 0:
            raise ValueError("review_sample_size nao pode ser negativo")
        if not 0.0 <= self.validation_abstention_quantile < 1.0:
            raise ValueError("validation_abstention_quantile deve estar em [0, 1)")
        object.__setattr__(self, "candidate_recall_ks", tuple(self.candidate_recall_ks))
        object.__setattr__(
            self, "parent_distance_boundaries", tuple(self.parent_distance_boundaries)
        )
        object.__setattr__(
            self, "time_gap_boundaries_seconds", tuple(self.time_gap_boundaries_seconds)
        )
        if not self.candidate_recall_ks or any(k < 1 for k in self.candidate_recall_ks):
            raise ValueError("candidate_recall_ks requer inteiros positivos")
        if tuple(sorted(set(self.candidate_recall_ks))) != self.candidate_recall_ks:
            raise ValueError("candidate_recall_ks deve ser crescente e sem duplicatas")
        for name, boundaries in (
            ("parent_distance_boundaries", self.parent_distance_boundaries),
            ("time_gap_boundaries_seconds", self.time_gap_boundaries_seconds),
        ):
            if not boundaries or any(value <= 0 for value in boundaries):
                raise ValueError(f"{name} requer limites positivos")
            if tuple(sorted(set(boundaries))) != boundaries:
                raise ValueError(f"{name} deve ser crescente e sem duplicatas")
        if self.competition_low_max >= self.competition_high_min:
            raise ValueError("competition_low_max deve ser menor que competition_high_min")
        if self.bootstrap_resamples < 0:
            raise ValueError("bootstrap_resamples nao pode ser negativo")
        if not 0.0 < self.bootstrap_confidence < 1.0:
            raise ValueError("bootstrap_confidence deve estar em (0, 1)")
        if self.bootstrap_unit not in {"message", "channel"}:
            raise ValueError("bootstrap_unit deve ser message ou channel")
        object.__setattr__(self, "approach_settings", self.approach_settings or {})

    def as_dict(self) -> dict[str, Any]:
        serialized = asdict(self)
        serialized["input_path"] = str(self.input_path)
        serialized["output_dir"] = str(self.output_dir)
        return serialized

    @classmethod
    def from_json(
        cls,
        path: Path,
        *,
        input_path: Path | None = None,
        output_dir: Path | None = None,
    ) -> "ExperimentConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        common = dict(payload.get("common", payload))
        common.pop("approaches", None)
        common.pop("study", None)
        if input_path is not None:
            common["input_path"] = input_path
        if output_dir is not None:
            common["output_dir"] = output_dir
        if "input_path" not in common or "output_dir" not in common:
            raise ValueError("config JSON requer input_path e output_dir")
        return cls(**common)
