from __future__ import annotations

import hashlib
import inspect
import json
import sys
from importlib.metadata import version
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from discord_disentanglement.approaches.base import DisentanglementApproach

from .config import ExperimentConfig
from .data import PreparedExperiment


ARTIFACT_FILENAMES: tuple[str, ...] = (
    "predicted_links.parquet",
    "message_assignments.parquet",
    "predicted_threads.parquet",
    "test_ranked_candidates.parquet",
    "metrics.json",
    "manifest.json",
    "review_sample.csv",
)


def rank_and_select_links(
    candidates: pd.DataFrame,
    scores: Any,
    *,
    approach_id: str,
    threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if len(candidates) != len(scores):
        raise ValueError("A abordagem retornou quantidade de scores diferente dos candidatos")
    ranked = candidates[
        [
            "source_message_id",
            "target_message_id",
            "source_split",
            "channel_id",
            "channel_name",
            "target_channel_id",
            "target_channel_name",
            "source_timestamp",
            "target_timestamp",
            "delta_seconds",
        ]
    ].copy()
    ranked["score"] = pd.Series(scores, index=ranked.index, dtype="float64")
    if ranked["score"].isna().any():
        raise ValueError("A abordagem retornou score NaN")
    ranked.sort_values(
        ["source_message_id", "score", "delta_seconds", "target_message_id"],
        ascending=[True, False, True, True],
        inplace=True,
        kind="stable",
    )
    ranked["rank_position"] = (
        ranked.groupby("source_message_id", sort=False).cumcount() + 1
    )
    ranked["score_second_best"] = ranked.groupby(
        "source_message_id", sort=False
    )["score"].transform(lambda values: values.iloc[1] if len(values) > 1 else 0.0)
    ranked["score_margin"] = ranked["score"] - ranked["score_second_best"]
    ranked["approach_id"] = approach_id

    best = ranked[ranked["rank_position"] == 1].copy()
    selected = best[best["score"] >= threshold].copy()
    selected["selection_threshold"] = float(threshold)
    output_columns = [
        "approach_id",
        "source_message_id",
        "target_message_id",
        "source_split",
        "channel_id",
        "channel_name",
        "target_channel_id",
        "target_channel_name",
        "source_timestamp",
        "target_timestamp",
        "delta_seconds",
        "score",
        "score_margin",
        "selection_threshold",
    ]
    return ranked.reset_index(drop=True), selected[output_columns].reset_index(drop=True)


def build_message_assignments(
    messages: pd.DataFrame,
    predicted_links: pd.DataFrame,
    *,
    approach_id: str,
) -> pd.DataFrame:
    parent_by_source = dict(
        zip(
            predicted_links["source_message_id"].astype(str),
            predicted_links["target_message_id"].astype(str),
            strict=False,
        )
    )
    score_by_source = dict(
        zip(
            predicted_links["source_message_id"].astype(str),
            predicted_links["score"].astype(float),
            strict=False,
        )
    )
    root_by_message: dict[str, str] = {}
    output_rows: list[dict[str, Any]] = []
    for message in messages.itertuples(index=False):
        message_id = str(message.message_id)
        parent_id = parent_by_source.get(message_id)
        # Candidate construction guarantees a prior parent; this explicit check keeps
        # corrupted inputs from silently creating a forward/cyclic assignment.
        root_id = root_by_message.get(parent_id, parent_id) if parent_id else message_id
        root_id = str(root_id or message_id)
        root_by_message[message_id] = root_id
        thread_hash = hashlib.sha1(
            f"{message.channel_key}\0{root_id}".encode("utf-8")
        ).hexdigest()[:12]
        output_rows.append(
            {
                "approach_id": approach_id,
                "message_id": message_id,
                "predicted_parent_message_id": parent_id,
                "predicted_parent_score": score_by_source.get(message_id),
                "predicted_thread_id": f"{approach_id.upper()}_{thread_hash}",
                "channel_id": message.channel_id,
                "channel_name": message.channel_name,
                "timestamp": message.timestamp,
                "split": message.split,
                "author_anon": message.author_anon,
            }
        )
    return pd.DataFrame.from_records(output_rows)


def build_predicted_threads(assignments: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for thread_id, group in assignments.groupby("predicted_thread_id", sort=False):
        ordered = group.sort_values(["timestamp", "message_id"], kind="stable")
        start = ordered["timestamp"].iloc[0]
        end = ordered["timestamp"].iloc[-1]
        rows.append(
            {
                "approach_id": ordered["approach_id"].iloc[0],
                "predicted_thread_id": thread_id,
                "root_message_id": ordered["message_id"].iloc[0],
                "channel_id": ordered["channel_id"].iloc[0],
                "channel_name": ordered["channel_name"].iloc[0],
                "start_timestamp": start,
                "end_timestamp": end,
                "duration_seconds": float((end - start).total_seconds()),
                "message_count": int(len(ordered)),
                "participant_count": int(ordered["author_anon"].nunique()),
                "split_membership": ",".join(
                    split
                    for split in ("train", "validation", "test")
                    if split in set(ordered["split"])
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


def build_review_sample(
    *,
    ranked_candidates: pd.DataFrame,
    predicted_links: pd.DataFrame,
    messages: pd.DataFrame,
    threshold: float,
    sample_size: int,
) -> pd.DataFrame:
    columns = [
        "review_id",
        "approach_id",
        "source_message_id",
        "predicted_target_message_id",
        "channel_id",
        "channel_name",
        "source_timestamp",
        "target_timestamp",
        "predicted_score",
        "score_margin",
        "link_selected",
        "source_text_normalized",
        "target_text_normalized",
        "reviewer_decision",
        "reviewer_notes",
    ]
    if sample_size == 0:
        return pd.DataFrame(columns=columns)
    best_test = ranked_candidates[
        (ranked_candidates["source_split"] == "test")
        & (ranked_candidates["rank_position"] == 1)
    ].copy()
    if best_test.empty:
        return pd.DataFrame(columns=columns)
    best_test["uncertainty"] = (best_test["score"] - threshold).abs()
    best_test["stable_tie_break"] = best_test.apply(
        lambda row: hashlib.sha1(
            f"{row['source_message_id']}\0{row['target_message_id']}".encode("utf-8")
        ).hexdigest(),
        axis=1,
    )
    best_test.sort_values(
        ["uncertainty", "stable_tie_break"], inplace=True, kind="stable"
    )
    selected_sources = set(predicted_links["source_message_id"].astype(str))
    text_by_id = messages.set_index("message_id")["content_normalized"].to_dict()
    sample_rows: list[dict[str, Any]] = []
    for row in best_test.head(sample_size).itertuples(index=False):
        source_id = str(row.source_message_id)
        target_id = str(row.target_message_id)
        review_id = hashlib.sha1(
            f"{row.approach_id}\0{source_id}\0{target_id}".encode("utf-8")
        ).hexdigest()[:16]
        sample_rows.append(
            {
                "review_id": review_id,
                "approach_id": row.approach_id,
                "source_message_id": source_id,
                "predicted_target_message_id": target_id,
                "channel_id": row.channel_id,
                "channel_name": row.channel_name,
                "source_timestamp": row.source_timestamp,
                "target_timestamp": row.target_timestamp,
                "predicted_score": round(float(row.score), 8),
                "score_margin": round(float(row.score_margin), 8),
                "link_selected": source_id in selected_sources,
                "source_text_normalized": text_by_id.get(source_id, ""),
                "target_text_normalized": text_by_id.get(target_id, ""),
                "reviewer_decision": "",
                "reviewer_notes": "",
            }
        )
    return pd.DataFrame.from_records(sample_rows, columns=columns)


def write_run_artifacts(
    *,
    run_dir: Path,
    config: ExperimentConfig,
    prepared: PreparedExperiment,
    approach: DisentanglementApproach,
    ranked_candidates: pd.DataFrame,
    predicted_links: pd.DataFrame,
    assignments: pd.DataFrame,
    predicted_threads: pd.DataFrame,
    metrics: dict[str, Any],
    review_sample: pd.DataFrame,
    scoring_diagnostics: dict[str, Any],
) -> dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: run_dir / name for name in ARTIFACT_FILENAMES}
    existing = [path for path in paths.values() if path.exists()]
    if existing and not config.overwrite:
        raise FileExistsError(
            "Artefatos ja existem e overwrite=False: "
            + ", ".join(str(path) for path in existing)
        )
    predicted_links.to_parquet(paths["predicted_links.parquet"], index=False)
    assignments.to_parquet(paths["message_assignments.parquet"], index=False)
    predicted_threads.to_parquet(paths["predicted_threads.parquet"], index=False)
    test_ranking_audit = ranked_candidates[
        ranked_candidates["source_split"] == "test"
    ].copy()
    test_ranking_audit.to_parquet(
        paths["test_ranked_candidates.parquet"], index=False
    )
    paths["metrics.json"].write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    review_sample.to_csv(paths["review_sample.csv"], index=False, encoding="utf-8")

    artifact_checksums = {
        name: _sha256_file(path)
        for name, path in paths.items()
        if name != "manifest.json"
    }
    approach_source_path = Path(inspect.getfile(approach.__class__))
    experiment_source_paths = {
        "approach_module": approach_source_path,
        "approach_base_module": approach_source_path.with_name("base.py"),
        "approach_math_module": approach_source_path.with_name("math_utils.py"),
        "artifact_module": Path(__file__),
        "runner_module": Path(__file__).with_name("runner.py"),
        "data_module": Path(__file__).with_name("data.py"),
        "metrics_module": Path(__file__).with_name("metrics.py"),
    }
    manifest = {
        "schema_version": "1.0",
        "implementation": {
            "version": "pilot_proxy_v1",
            "source_sha256": {
                name: _sha256_file(path)
                for name, path in experiment_source_paths.items()
            },
            "deterministic_algorithms": True,
            "random_seed_recorded_for_future_stochastic_extensions": config.random_seed,
            "runtime_versions": {
                "python": sys.version.split()[0],
                "numpy": version("numpy"),
                "pandas": version("pandas"),
                "pyarrow": version("pyarrow"),
            },
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "study_scope": {
            "guild_id": config.guild_id,
            "guild_name": config.guild_name,
            "initial_target": "Neo4j Discord guild",
        },
        "approach": approach.manifest_metadata(),
        "effective_config": config.as_dict(),
        "input": {
            "path": str(config.input_path),
            "filtered_guild_snapshot_sha256": prepared.input_fingerprint,
        },
        "common_candidate_protocol": {
            "same_channel_only": True,
            "strictly_past_only": True,
            "candidate_fingerprint": prepared.candidate_fingerprint,
            "candidate_pair_count": int(len(prepared.candidates)),
            "prediction_columns": list(prepared.prediction_columns),
            "reply_or_thread_columns_present": False,
            "tfidf_idf_fit_split": "train_only",
            "candidate_cap_selection": "half_recent_then_topical_without_labels",
        },
        "temporal_split": prepared.split_summary,
        "label_isolation": {
            "test_reply_fields_visible_to_approach": False,
            "test_reply_fields_used_for_candidate_generation": False,
            "test_reply_fields_used_for_metrics_only": True,
            "validation_reply_fields_used": False,
            "train_reply_fields_used_by_this_approach": approach.uses_direct_reply_training,
        },
        "data_quality": prepared.data_quality,
        "scoring_diagnostics": scoring_diagnostics,
        "predicted_link_invariants": {
            "cross_channel_link_count": _cross_channel_count(predicted_links),
            "non_past_link_count": int((predicted_links["delta_seconds"] <= 0).sum()),
        },
        "artifacts": artifact_checksums,
    }
    paths["manifest.json"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return paths


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cross_channel_count(links: pd.DataFrame) -> int:
    if links.empty:
        return 0
    source_key = links["channel_id"].fillna("").astype(str)
    target_key = links["target_channel_id"].fillna("").astype(str)
    source_key = source_key.where(
        source_key.ne(""), "name:" + links["channel_name"].fillna("").astype(str).str.casefold()
    )
    target_key = target_key.where(
        target_key.ne(""),
        "name:" + links["target_channel_name"].fillna("").astype(str).str.casefold(),
    )
    return int(source_key.ne(target_key).sum())
