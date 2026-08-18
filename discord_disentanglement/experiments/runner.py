from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from discord_disentanglement.approaches import (
    APPROACH_IDS,
    ApproachFitData,
    DisentanglementApproach,
    create_approach,
)

from .artifacts import (
    ARTIFACT_FILENAMES,
    build_message_assignments,
    build_predicted_threads,
    build_review_sample,
    rank_and_select_links,
    write_run_artifacts,
)
from .config import ExperimentConfig
from .data import PreparedExperiment, prepare_experiment
from .metrics import compute_test_metrics


@dataclass(slots=True)
class ExperimentRunResult:
    approach_id: str
    run_dir: Path
    artifacts: dict[str, Path]
    metrics: dict[str, Any]
    candidate_fingerprint: str


@dataclass(slots=True)
class AllExperimentsResult:
    runs: dict[str, ExperimentRunResult]
    comparison_csv: Path
    comparison_markdown: Path


def run_experiment(
    config: ExperimentConfig,
    approach: str | DisentanglementApproach,
) -> ExperimentRunResult:
    """Prepare the shared protocol and execute one isolated approach module."""

    instance = create_approach(approach) if isinstance(approach, str) else approach
    _preflight_outputs(config, (instance.approach_id,), include_comparison=False)
    prepared = prepare_experiment(config)
    return _run_prepared(config, prepared, instance)


def run_all(
    config: ExperimentConfig,
    approaches: Iterable[str] = APPROACH_IDS,
) -> AllExperimentsResult:
    """Run approaches on one immutable preparation and write CSV/Markdown comparison."""

    approach_ids = tuple(approaches)
    if len(set(approach_ids)) != len(approach_ids):
        raise ValueError("A lista de abordagens contem duplicatas")
    _preflight_outputs(config, approach_ids, include_comparison=True)
    prepared = prepare_experiment(config)
    runs: dict[str, ExperimentRunResult] = {}
    for approach_id in approach_ids:
        instance = create_approach(approach_id)
        result = _run_prepared(config, prepared, instance)
        runs[approach_id] = result
    comparison_csv, comparison_markdown = write_comparison(config.output_dir, runs)
    return AllExperimentsResult(
        runs=runs,
        comparison_csv=comparison_csv,
        comparison_markdown=comparison_markdown,
    )


def _run_prepared(
    config: ExperimentConfig,
    prepared: PreparedExperiment,
    approach: DisentanglementApproach,
) -> ExperimentRunResult:
    train_candidates = prepared.candidates[
        prepared.candidates["source_split"] == "train"
    ].reset_index(drop=True)
    validation_candidates = prepared.candidates[
        prepared.candidates["source_split"] == "validation"
    ].reset_index(drop=True)
    if approach.uses_direct_reply_training:
        train_gold = prepared.direct_reply_gold[
            prepared.direct_reply_gold["source_split"] == "train"
        ][["source_message_id", "target_message_id"]].reset_index(drop=True)
    else:
        train_gold = pd.DataFrame(
            columns=["source_message_id", "target_message_id"]
        )
    approach.fit(
        ApproachFitData(
            train_candidates=train_candidates,
            validation_candidates=validation_candidates,
            train_gold=train_gold,
            random_seed=config.random_seed,
        )
    )
    threshold = _calibrate_label_free_threshold(
        approach,
        validation_candidates,
        abstention_quantile=config.validation_abstention_quantile,
    )
    scored = approach.score(prepared.candidates)
    ranked, predicted_links = rank_and_select_links(
        prepared.candidates,
        scored.scores,
        approach_id=approach.approach_id,
        threshold=threshold,
    )
    assignments = build_message_assignments(
        prepared.messages,
        predicted_links,
        approach_id=approach.approach_id,
    )
    predicted_threads = build_predicted_threads(assignments)
    metrics = compute_test_metrics(
        approach_id=approach.approach_id,
        ranked_candidates=ranked,
        predicted_links=predicted_links,
        message_assignments=assignments,
        direct_reply_gold=prepared.direct_reply_gold,
        selection_threshold=threshold,
        abstention_quantile=config.validation_abstention_quantile,
    )
    review_sample = build_review_sample(
        ranked_candidates=ranked,
        predicted_links=predicted_links,
        messages=prepared.messages,
        threshold=threshold,
        sample_size=config.review_sample_size,
    )
    run_dir = config.output_dir / approach.approach_id
    artifacts = write_run_artifacts(
        run_dir=run_dir,
        config=config,
        prepared=prepared,
        approach=approach,
        ranked_candidates=ranked,
        predicted_links=predicted_links,
        assignments=assignments,
        predicted_threads=predicted_threads,
        metrics=metrics,
        review_sample=review_sample,
        scoring_diagnostics=scored.diagnostics,
    )
    return ExperimentRunResult(
        approach_id=approach.approach_id,
        run_dir=run_dir,
        artifacts=artifacts,
        metrics=metrics,
        candidate_fingerprint=prepared.candidate_fingerprint,
    )


def _calibrate_label_free_threshold(
    approach: DisentanglementApproach,
    validation_candidates: pd.DataFrame,
    *,
    abstention_quantile: float,
) -> float:
    if validation_candidates.empty:
        raise ValueError(
            "Nao ha candidatos no split de validacao para calibrar abstencao sem rotulos"
        )
    validation_score = approach.score(validation_candidates).scores
    score_frame = validation_candidates[["source_message_id"]].copy()
    score_frame["score"] = validation_score
    best_scores = score_frame.groupby("source_message_id", sort=False)["score"].max()
    if best_scores.empty:
        raise ValueError("Nenhum source de validacao recebeu score para calibracao")
    threshold = float(np.quantile(best_scores.to_numpy(dtype=float), abstention_quantile))
    approach.effective_link_threshold = threshold
    approach.threshold_diagnostics = {
        "method": "label_free_validation_best_score_quantile",
        "abstention_quantile": float(abstention_quantile),
        "validation_source_count": int(len(best_scores)),
        "effective_threshold": threshold,
        "validation_reply_labels_used": 0,
    }
    return threshold


def _preflight_outputs(
    config: ExperimentConfig,
    approach_ids: Iterable[str],
    *,
    include_comparison: bool,
) -> None:
    if config.overwrite:
        return
    targets = [
        config.output_dir / approach_id / artifact_name
        for approach_id in approach_ids
        for artifact_name in ARTIFACT_FILENAMES
    ]
    if include_comparison:
        targets.extend(
            [config.output_dir / "comparison.csv", config.output_dir / "comparison.md"]
        )
    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(
            "A execucao recusou sobrescrever artefatos existentes. Use overwrite=True "
            "explicitamente se essa substituicao for intencional: "
            + ", ".join(str(path) for path in existing)
        )


def write_comparison(
    output_dir: Path,
    runs: dict[str, ExperimentRunResult],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for approach_id, result in runs.items():
        metrics = result.metrics
        rows.append(
            {
                "approach_id": approach_id,
                "fidelity": "pilot_proxy",
                "candidate_fingerprint": result.candidate_fingerprint,
                "evaluation_split": metrics["evaluation_split"],
                "selection_threshold": metrics["selection_threshold"],
                "test_message_count": metrics["test_message_count"],
                "test_candidate_pair_count": metrics["test_candidate_pair_count"],
                "test_explicit_reply_count": metrics["test_explicit_reply_count"],
                "test_explicit_reply_candidate_coverage": metrics[
                    "test_explicit_reply_candidate_coverage"
                ],
                "test_recall_at_1": metrics["test_recall_at_1"],
                "test_recall_at_3": metrics["test_recall_at_3"],
                "test_recall_at_5": metrics["test_recall_at_5"],
                "test_mrr": metrics["test_mrr"],
                "test_selected_parent_accuracy_on_explicit_sources": metrics[
                    "test_selected_parent_accuracy_on_explicit_sources"
                ],
                "test_predicted_link_count": metrics["test_predicted_link_count"],
                "test_predicted_thread_count": metrics["test_predicted_thread_count"],
            }
        )
    comparison = pd.DataFrame.from_records(rows)
    csv_path = output_dir / "comparison.csv"
    markdown_path = output_dir / "comparison.md"
    comparison.to_csv(csv_path, index=False, encoding="utf-8")
    markdown_path.write_text(_comparison_markdown(comparison), encoding="utf-8")
    return csv_path, markdown_path


def _comparison_markdown(comparison: pd.DataFrame) -> str:
    heading = (
        "# Comparacao do piloto de disentanglement — Neo4j\n\n"
        "Todas as linhas usam o mesmo universo de candidatos e somente o split temporal "
        "held-out de teste (20%) nas metricas. `fidelity=pilot_proxy`: os modulos nao "
        "alegam reproducao fiel dos artigos. Replies explicitos sao referencia positiva "
        "silver, nao ground truth conversacional completo.\n\n"
    )
    if comparison.empty:
        return heading + "Nenhuma abordagem executada.\n"
    display_columns = [
        "approach_id",
        "test_recall_at_1",
        "test_recall_at_3",
        "test_mrr",
        "test_predicted_link_count",
        "test_predicted_thread_count",
    ]
    header = "| " + " | ".join(display_columns) + " |\n"
    divider = "| " + " | ".join(["---"] * len(display_columns)) + " |\n"
    rows: list[str] = []
    for record in comparison[display_columns].to_dict(orient="records"):
        values = []
        for column in display_columns:
            value = record[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        rows.append("| " + " | ".join(values) + " |")
    fingerprint_count = comparison["candidate_fingerprint"].nunique()
    verification = (
        "\n\nVerificacao do contrato comum: "
        + ("aprovada" if fingerprint_count == 1 else "FALHOU")
        + f" ({fingerprint_count} fingerprint(s) de candidatos).\n"
    )
    return heading + header + divider + "\n".join(rows) + verification
