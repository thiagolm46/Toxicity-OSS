"""Read-only access to versioned experiment artifacts for the Streamlit UI."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import pandas as pd

from discord_disentanglement.experiments.config import ExperimentConfig
from discord_disentanglement.experiments.data import load_experiment_messages


@dataclass(frozen=True, slots=True)
class LoadedRun:
    approach_id: str
    run_dir: Path
    metrics: dict[str, Any]
    manifest: dict[str, Any]
    predicted_links: pd.DataFrame
    assignments: pd.DataFrame
    predicted_threads: pd.DataFrame
    ranked_candidates: pd.DataFrame
    gold_outcomes: pd.DataFrame
    silver_projection: pd.DataFrame


def discover_experiments(root: Path) -> list[Path]:
    """Find completed experiment directories, newest first."""
    base = Path(root)
    if not base.exists():
        return []
    found = {path.parent.resolve() for path in base.rglob("comparison.csv")}
    return sorted(found, key=lambda path: path.stat().st_mtime, reverse=True)


class ExperimentRepository:
    """Small read-only façade over one standard experiment directory."""

    def __init__(self, experiment_dir: Path) -> None:
        self.experiment_dir = Path(experiment_dir).resolve()
        comparison_path = self.experiment_dir / "comparison.csv"
        if not comparison_path.exists():
            raise FileNotFoundError(f"comparison.csv nao encontrado: {comparison_path}")
        self.comparison = pd.read_csv(comparison_path)

    @property
    def approach_ids(self) -> tuple[str, ...]:
        return tuple(self.comparison["approach_id"].astype(str))

    def load_run(self, approach_id: str) -> LoadedRun:
        if approach_id not in self.approach_ids:
            raise ValueError(f"Abordagem ausente do experimento: {approach_id}")
        run_dir = self.experiment_dir / approach_id
        manifest = _read_json(run_dir / "manifest.json")
        metrics = _read_json(run_dir / "metrics.json")
        return LoadedRun(
            approach_id=approach_id,
            run_dir=run_dir,
            metrics=metrics,
            manifest=manifest,
            predicted_links=pd.read_parquet(run_dir / "predicted_links.parquet"),
            assignments=pd.read_parquet(run_dir / "message_assignments.parquet"),
            predicted_threads=pd.read_parquet(run_dir / "predicted_threads.parquet"),
            ranked_candidates=pd.read_parquet(run_dir / "test_ranked_candidates.parquet"),
            gold_outcomes=pd.read_parquet(run_dir / "test_gold_outcomes.parquet"),
            silver_projection=pd.read_parquet(run_dir / "silver_projection.parquet"),
        )

    def load_messages(self, approach_id: str | None = None) -> pd.DataFrame:
        selected = approach_id or self.approach_ids[0]
        manifest = _read_json(self.experiment_dir / selected / "manifest.json")
        config_payload = dict(manifest["effective_config"])
        config_payload["input_path"] = _resolve_input_path(
            Path(config_payload["input_path"]), self.experiment_dir
        )
        config_payload["output_dir"] = self.experiment_dir
        allowed = {item.name for item in fields(ExperimentConfig)}
        config = ExperimentConfig(
            **{key: value for key, value in config_payload.items() if key in allowed}
        )
        messages = load_experiment_messages(config)
        return messages[
            [
                "message_id",
                "channel_id",
                "channel_name",
                "channel_key",
                "timestamp",
                "content_normalized",
                "author_anon",
                "split",
            ]
        ].copy()

    def link_inspector(
        self,
        run: LoadedRun,
        messages: pd.DataFrame,
        source_message_id: str,
        *,
        top_k: int = 10,
    ) -> pd.DataFrame:
        ranking = run.ranked_candidates[
            run.ranked_candidates["source_message_id"].astype(str)
            == str(source_message_id)
        ].nsmallest(top_k, "rank_position")
        lookup = messages.set_index("message_id")
        selected_links = set(
            zip(
                run.predicted_links["source_message_id"].astype(str),
                run.predicted_links["target_message_id"].astype(str),
                strict=False,
            )
        )
        rows: list[dict[str, Any]] = []
        for item in ranking.itertuples(index=False):
            candidate_id = str(item.target_message_id)
            message = lookup.loc[candidate_id]
            rows.append(
                {
                    "rank": int(item.rank_position),
                    "candidate_message_id": candidate_id,
                    "author": message["author_anon"],
                    "timestamp": message["timestamp"],
                    "message": message["content_normalized"],
                    "score": float(item.score),
                    "message_distance": int(item.message_distance),
                    "time_gap_seconds": float(item.time_gap_seconds),
                    "is_top_ranked": int(item.rank_position) == 1,
                    "is_selected_parent": (
                        str(source_message_id), candidate_id
                    )
                    in selected_links,
                    "is_silver_parent": bool(item.is_silver_parent),
                }
            )
        return pd.DataFrame.from_records(rows)

    def method_disagreement(self, source_message_id: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for approach_id in self.approach_ids:
            run = self.load_run(approach_id)
            ranking = run.ranked_candidates[
                run.ranked_candidates["source_message_id"].astype(str)
                == str(source_message_id)
            ]
            best = ranking.nsmallest(1, "rank_position")
            rows.append(
                {
                    "approach_id": approach_id,
                    "predicted_parent": (
                        str(best.iloc[0]["target_message_id"]) if not best.empty else None
                    ),
                    "score": float(best.iloc[0]["score"]) if not best.empty else None,
                    "silver_parent": (
                        str(best.iloc[0]["silver_parent_message_id"])
                        if not best.empty and pd.notna(best.iloc[0]["silver_parent_message_id"])
                        else None
                    ),
                    "correct": bool(best.iloc[0]["is_silver_parent"])
                    if not best.empty
                    else False,
                }
            )
        return pd.DataFrame.from_records(rows)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_input_path(input_path: Path, experiment_dir: Path) -> Path:
    if input_path.is_absolute():
        return input_path
    for parent in (experiment_dir, *experiment_dir.parents):
        if (parent / "pyproject.toml").exists():
            return (parent / input_path).resolve()
    candidate = (Path.cwd() / input_path).resolve()
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Nao foi possivel resolver a entrada relativa {input_path} a partir de {experiment_dir}"
    )
