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
