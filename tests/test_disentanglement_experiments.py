from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from discord_disentanglement.approaches import APPROACH_IDS, ApproachFitData, create_approach
from discord_disentanglement.approaches.base import FORBIDDEN_PREDICTION_COLUMNS
from discord_disentanglement.experiments import ExperimentConfig, run_all, run_experiment
from discord_disentanglement.experiments.data import PreparedExperiment, prepare_experiment


GUILD_ID = "787399249741479977"


def _write_synthetic_parquet(path: Path, *, alternate_test_gold: bool = False) -> None:
    rows: list[dict[str, object]] = []
    topics = (
        "cypher match graph relationship query",
        "docker server port container error",
        "python driver transaction session code",
    )
    reply_positions = {8, 12, 18, 24, 30, 34, 40, 46, 52, 58}
    for index in range(60):
        channel_number = index % 2
        channel_id = f"channel-{channel_number}"
        topic = topics[(index // 4) % len(topics)]
        content = f"question {index}: {topic}?" if index % 4 == 0 else f"update {index} about {topic}"
        referenced_message_id: str | None = None
        if index in reply_positions:
            content_target_index = index - 2
            target_index = content_target_index
            if alternate_test_gold and index >= 48:
                target_index = index - 4
            referenced_message_id = f"m{target_index:03d}"
            # Content is deliberately independent of the alternative held-out gold.
            target_topic = topics[(content_target_index // 4) % len(topics)]
            content = f"try this answer for {target_topic} because it fixes the issue"
        rows.append(
            {
                "guild_id": GUILD_ID,
                "guild_name": "Neo4j",
                "message_id": f"m{index:03d}",
                "channel_id": channel_id,
                "channel_name": "help" if channel_number == 0 else "developers",
                "author_id": f"user-{(index + channel_number) % 7}",
                "timestamp": pd.Timestamp("2026-01-01T00:00:00Z")
                + pd.Timedelta(minutes=index),
                "content": content,
                "referenced_message_id": referenced_message_id,
                "mentions_json": "[]",
                "attachments_json": "[]",
                "embeds_json": "[]",
            }
        )
    # A different guild at the same time must be filtered before candidate generation.
    rows.append(
        {
            "guild_id": "other-guild",
            "guild_name": "Other",
            "message_id": "outside",
            "channel_id": "channel-0",
            "channel_name": "help",
            "author_id": "outsider",
            "timestamp": pd.Timestamp("2026-01-01T00:20:30Z"),
            "content": "must never become a candidate",
            "referenced_message_id": None,
            "mentions_json": "[]",
            "attachments_json": "[]",
            "embeds_json": "[]",
        }
    )
    pd.DataFrame.from_records(rows).to_parquet(path, index=False)


def _config(input_path: Path, output_dir: Path) -> ExperimentConfig:
    return ExperimentConfig(
        input_path=input_path,
        output_dir=output_dir,
        guild_id=GUILD_ID,
        max_previous_messages=12,
        max_candidates_per_message=8,
        max_time_delta_hours=2.0,
        review_sample_size=6,
    )


def test_common_candidates_are_same_channel_strictly_past_and_label_free(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "messages.parquet"
    _write_synthetic_parquet(input_path)
    prepared = prepare_experiment(_config(input_path, tmp_path / "out"))

    assert prepared.split_summary["counts"] == {
        "train": 36,
        "validation": 12,
        "test": 12,
    }
    assert prepared.messages["split"].tolist() == (
        ["train"] * 36 + ["validation"] * 12 + ["test"] * 12
    )
    assert not FORBIDDEN_PREDICTION_COLUMNS.intersection(prepared.candidates.columns)
    assert (prepared.candidates["target_timestamp"] < prepared.candidates["source_timestamp"]).all()

    channel_by_message = prepared.messages.set_index("message_id")["channel_key"]
    assert all(
        channel_by_message[source] == channel_by_message[target]
        for source, target in zip(
            prepared.candidates["source_message_id"],
            prepared.candidates["target_message_id"],
            strict=True,
        )
    )
    assert "outside" not in set(prepared.candidates["source_message_id"])
    assert "outside" not in set(prepared.candidates["target_message_id"])
    assert prepared.data_quality["direct_reply_references_raw"] == 10
    assert prepared.data_quality["direct_reply_references_valid_same_channel_past"] == 10
    assert prepared.data_quality["direct_reply_target_missing_from_filtered_guild"] == 0


def test_run_all_writes_isolated_contract_and_test_only_metrics(tmp_path: Path) -> None:
    input_path = tmp_path / "messages.parquet"
    output_dir = tmp_path / "experiments"
    _write_synthetic_parquet(input_path)

    result = run_all(_config(input_path, output_dir))

    assert set(result.runs) == set(APPROACH_IDS)
    assert result.comparison_csv.exists()
    assert result.comparison_markdown.exists()
    comparison = pd.read_csv(result.comparison_csv)
    assert comparison["candidate_fingerprint"].nunique() == 1
    assert set(comparison["evaluation_split"]) == {"test"}
    assert set(comparison["fidelity"]) == {"pilot_proxy"}

    ranking_score_signatures: list[tuple[float, ...]] = []
    for approach_id, run in result.runs.items():
        expected = {
            "predicted_links.parquet",
            "message_assignments.parquet",
            "predicted_threads.parquet",
            "test_ranked_candidates.parquet",
            "metrics.json",
            "manifest.json",
            "review_sample.csv",
        }
        assert expected == {path.name for path in run.artifacts.values()}
        assert all(path.exists() for path in run.artifacts.values())
        links = pd.read_parquet(run.artifacts["predicted_links.parquet"])
        assignments = pd.read_parquet(run.artifacts["message_assignments.parquet"])
        threads = pd.read_parquet(run.artifacts["predicted_threads.parquet"])
        ranking_audit = pd.read_parquet(
            run.artifacts["test_ranked_candidates.parquet"]
        ).sort_values(["source_message_id", "target_message_id"])
        metrics = json.loads(run.artifacts["metrics.json"].read_text(encoding="utf-8"))
        manifest = json.loads(run.artifacts["manifest.json"].read_text(encoding="utf-8"))

        assert set(links["approach_id"]) <= {approach_id}
        assert set(assignments["approach_id"]) == {approach_id}
        assert set(threads["approach_id"]) == {approach_id}
        assert not FORBIDDEN_PREDICTION_COLUMNS.intersection(links.columns)
        assert (links["target_timestamp"] < links["source_timestamp"]).all()
        assert (
            links["channel_id"].fillna("").astype(str)
            == links["target_channel_id"].fillna("").astype(str)
        ).all()
        assert metrics["evaluation_split"] == "test"
        assert metrics["scope"] == "held_out_test_only"
        assert metrics["test_message_count"] == 12
        assert metrics["test_cross_channel_predicted_link_count"] == 0
        assert metrics["test_non_past_predicted_link_count"] == 0
        assert manifest["approach"]["fidelity"] == "pilot_proxy"
        assert manifest["approach"]["effective_link_threshold"] == metrics["selection_threshold"]
        assert manifest["common_candidate_protocol"]["same_channel_only"] is True
        assert manifest["common_candidate_protocol"]["strictly_past_only"] is True
        assert manifest["label_isolation"]["test_reply_fields_visible_to_approach"] is False
        assert manifest["label_isolation"]["test_reply_fields_used_for_metrics_only"] is True
        assert manifest["predicted_link_invariants"]["cross_channel_link_count"] == 0
        assert manifest["predicted_link_invariants"]["non_past_link_count"] == 0
        ranking_score_signatures.append(
            tuple(ranking_audit["score"].round(10).astype(float).tolist())
        )

    # Each module has its own method ID, scores/threshold and isolated output.
    assert len(set(ranking_score_signatures)) == 3
    with pytest.raises(FileExistsError, match="overwrite=True"):
        run_all(_config(input_path, output_dir))


def test_changing_only_test_reply_gold_does_not_change_weak_predictions(
    tmp_path: Path,
) -> None:
    input_a = tmp_path / "messages_a.parquet"
    input_b = tmp_path / "messages_b.parquet"
    _write_synthetic_parquet(input_a, alternate_test_gold=False)
    _write_synthetic_parquet(input_b, alternate_test_gold=True)

    config_a = _config(input_a, tmp_path / "run_a")
    config_b = _config(input_b, tmp_path / "run_b")
    prepared_a = prepare_experiment(config_a)
    prepared_b = prepare_experiment(config_b)
    assert prepared_a.candidate_fingerprint == prepared_b.candidate_fingerprint

    def fitted_scores(prepared: PreparedExperiment) -> np.ndarray:
        approach = create_approach("weak_supervision")
        candidates = prepared.candidates
        gold = prepared.direct_reply_gold
        approach.fit(
            ApproachFitData(
                train_candidates=candidates.query("source_split == 'train'").reset_index(drop=True),
                validation_candidates=candidates.query(
                    "source_split == 'validation'"
                ).reset_index(drop=True),
                train_gold=gold.query("source_split == 'train'")[
                    ["source_message_id", "target_message_id"]
                ].reset_index(drop=True),
                random_seed=42,
            )
        )
        return approach.score(candidates).scores

    np.testing.assert_array_equal(fitted_scores(prepared_a), fitted_scores(prepared_b))

    run_a = run_experiment(config_a, "weak_supervision")
    run_b = run_experiment(config_b, "weak_supervision")
    links_a = pd.read_parquet(run_a.artifacts["predicted_links.parquet"])
    links_b = pd.read_parquet(run_b.artifacts["predicted_links.parquet"])
    comparable_columns = [
        "source_message_id",
        "target_message_id",
        "source_split",
        "score",
        "score_margin",
    ]
    pd.testing.assert_frame_equal(
        links_a[comparable_columns],
        links_b[comparable_columns],
        check_exact=True,
    )
    gold_a = prepared_a.direct_reply_gold.query("source_split == 'test'")
    gold_b = prepared_b.direct_reply_gold.query("source_split == 'test'")
    assert not gold_a[["source_message_id", "target_message_id"]].equals(
        gold_b[["source_message_id", "target_message_id"]]
    )

    run_c = run_experiment(_config(input_a, tmp_path / "run_c"), "weak_supervision")
    for artifact_name in (
        "predicted_links.parquet",
        "message_assignments.parquet",
        "predicted_threads.parquet",
        "test_ranked_candidates.parquet",
    ):
        pd.testing.assert_frame_equal(
            pd.read_parquet(run_a.artifacts[artifact_name]),
            pd.read_parquet(run_c.artifacts[artifact_name]),
            check_exact=True,
        )
    assert run_a.metrics == run_c.metrics
