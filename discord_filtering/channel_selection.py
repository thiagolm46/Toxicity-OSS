from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from discord_filtering.storage import atomic_write_bytes, sha256_file


RULE_VERSION = "historical_channels_500_and_5.v1"
DECISION_COLUMNS = (
    "guild_id", "guild_name", "channel_id", "channel_name", "total_messages",
    "interacting_authors", "manual_excluded", "low_activity_excluded", "retained", "decision_reason",
)
BUNDLE_FILES = (
    "statistics.parquet", "exclusions.txt", "statistics.manifest.json",
    "corpus.manifest.json", "decisions.csv", "audit.json",
)


def channel_decisions(
    statistics: pd.DataFrame,
    excluded_names: set[str],
    *,
    minimum_messages: int = 500,
    minimum_interacting_authors: int = 5,
) -> pd.DataFrame:
    required = {"guild_id", "channel_id", "channel_name", "guild_name", "total_messages", "interacting_authors"}
    missing = required - set(statistics.columns)
    if missing:
        raise ValueError(f"missing statistics columns: {', '.join(sorted(missing))}")
    decisions = statistics.copy()
    for field in ("guild_id", "channel_id"):
        values = decisions[field].astype("string")
        if values.isna().any() or values.str.strip().eq("").any() or values.ne(values.str.strip()).any():
            raise ValueError(f"missing or noncanonical identifier: {field}")
        decisions[field] = values
    if decisions.channel_id.duplicated().any():
        raise ValueError("channel_id must be globally unique for historical channel-only removal")
    if decisions[["channel_name", "guild_name"]].isna().any().any():
        raise ValueError("channel_name and guild_name must not be missing")
    for field in ("total_messages", "interacting_authors"):
        values = pd.to_numeric(decisions[field], errors="raise")
        if pd.api.types.is_bool_dtype(values.dtype) or not np.isfinite(values).all() or (values < 0).any() or (values % 1 != 0).any():
            raise ValueError(f"{field} must contain finite nonnegative integer counts")
        decisions[field] = values.astype("int64")
    decisions["manual_excluded"] = decisions.channel_name.isin(excluded_names)
    decisions["low_activity_excluded"] = (
        (decisions.total_messages < minimum_messages)
        & (decisions.interacting_authors < minimum_interacting_authors)
    )
    decisions["retained"] = ~(decisions.manual_excluded | decisions.low_activity_excluded)
    decisions["decision_reason"] = np.select(
        [decisions.manual_excluded & decisions.low_activity_excluded,
         decisions.manual_excluded, decisions.low_activity_excluded],
        ["manual_and_low_activity", "manual_name", "low_activity"],
        default="retained",
    )
    return decisions.sort_values(["guild_id", "channel_id"]).reset_index(drop=True)


def _read_names(path: Path) -> set[str]:
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _counts(decisions: pd.DataFrame) -> dict:
    return {
        "source_channels": len(decisions),
        "manual_excluded": int(decisions.manual_excluded.sum()),
        "low_activity_excluded": int(decisions.low_activity_excluded.sum()),
        "overlap": int((decisions.manual_excluded & decisions.low_activity_excluded).sum()),
        "excluded_channels": int((~decisions.retained).sum()),
        "retained_channels": int(decisions.retained.sum()),
        "source_messages": int(decisions.total_messages.sum()),
        "removed_messages": int(decisions.loc[~decisions.retained, "total_messages"].sum()),
        "remaining_messages": int(decisions.loc[decisions.retained, "total_messages"].sum()),
        "retained_channels_below_500_messages": int((decisions.retained & decisions.total_messages.lt(500)).sum()),
    }


def _file_reference(manifest: dict, path: Path) -> dict:
    references = [*manifest.get("inputs", []), manifest["output"]]
    matches = [item for item in references if Path(item["path"]).name == path.name]
    if len(matches) != 1:
        raise ValueError(f"missing or ambiguous manifest reference: {path.name}")
    return matches[0]


def _check_hash(path: Path, expected: str) -> str:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"hash mismatch: {path.name}")
    return actual


def _message_counts(path: Path) -> pd.DataFrame:
    with duckdb.connect() as connection:
        connection.from_parquet(str(path)).create_view("messages")
        return connection.execute("""
            SELECT cast(guild_id AS VARCHAR) AS guild_id,
                   cast(channel_id AS VARCHAR) AS channel_id, count(*) AS total_messages
            FROM messages GROUP BY guild_id, channel_id
            ORDER BY guild_id, channel_id
        """).fetchdf().astype({"guild_id": "string", "channel_id": "string"})


def _assert_counts(actual: pd.DataFrame, expected: pd.DataFrame, label: str) -> None:
    fields = ["guild_id", "channel_id", "total_messages"]
    expected = expected[fields].sort_values(fields[:2]).reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
    except AssertionError as error:
        raise ValueError(f"{label}: channel membership or message counts disagree") from error


def freeze_historical_selection(
    statistics_path: str | Path,
    exclusion_path: str | Path,
    source_path: str | Path,
    retained_path: str | Path,
    output_dir: str | Path,
) -> dict:
    statistics_path, exclusion_path, source_path, retained_path, output = (
        Path(path).resolve() for path in (statistics_path, exclusion_path, source_path, retained_path, output_dir)
    )
    if output.exists():
        raise FileExistsError(f"bundle directory already exists: {output}")
    statistics_manifest_path = statistics_path.with_name(statistics_path.name + ".manifest.json")
    corpus_manifest_path = retained_path.with_name(retained_path.name + ".manifest.json")
    statistics_manifest = json.loads(statistics_manifest_path.read_text(encoding="utf-8"))
    corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    parameters = corpus_manifest["parameters"]
    if parameters["minimum_messages"] != 500 or parameters["minimum_interacting_authors"] != 5:
        raise ValueError("manifest is not the historical 500 AND 5 rule")
    condition = "total_messages < minimum_messages AND interacting_authors < minimum_interacting_authors"
    if parameters.get("low_activity_condition") != condition:
        raise ValueError("historical conjunction differs from the declared rule")
    checked = {}
    for path in (statistics_path, exclusion_path, source_path, retained_path):
        checked[path.name] = _check_hash(path, _file_reference(corpus_manifest, path)["sha256"])
    _check_hash(statistics_path, statistics_manifest["output"]["sha256"])
    if _file_reference(statistics_manifest, source_path)["sha256"] != checked[source_path.name]:
        raise ValueError("statistics and corpus manifests refer to different source messages")
    statistics = pd.read_parquet(statistics_path)
    names = _read_names(exclusion_path)
    decisions = channel_decisions(statistics, names)
    counts = _counts(decisions)
    unmatched = sorted(names - set(decisions.channel_name))
    if unmatched:
        raise ValueError(f"unmatched manual exclusion names: {unmatched}")
    for field in ("source_messages", "removed_messages", "remaining_messages"):
        if corpus_manifest["counts"][field] != counts[field]:
            raise ValueError(f"historical manifest count mismatch: {field}")
    if parameters["excluded_channel_id_count"] != counts["excluded_channels"]:
        raise ValueError("historical excluded channel count mismatch")
    if statistics_manifest["counts"]["source_rows"] != counts["source_messages"] or statistics_manifest["counts"]["total_channels"] != len(decisions):
        raise ValueError("statistics manifest counts disagree")
    _assert_counts(_message_counts(source_path), decisions, "source corpus")
    _assert_counts(_message_counts(retained_path), decisions.loc[decisions.retained], "retained corpus")
    audit = {
        "rule_version": RULE_VERSION,
        "counts": counts,
        "distinct_manual_names": len(names),
        "unmatched_manual_names": unmatched,
        "verification": "actual source and retained hashes, channel membership and per-channel row counts match the frozen statistics and decisions",
        "reproducibility_scope": "decision replay from frozen historical statistics; not reconstruction of interacting_authors or manual judgments",
        "historical_metric_definition": "unrecovered",
        "exploratory_rule": {
            "condition": "total_messages >= 552 AND unique_authors >= 3",
            "role": "exploratory inspection only; not an input mask to the final selection",
            "threshold_change_rationale": "no contemporaneous justification recovered; no claim of statistical calibration or equivalence",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".channel-selection-", dir=output.parent) as temporary:
        staging = Path(temporary)
        for filename, path in (
            ("statistics.parquet", statistics_path), ("exclusions.txt", exclusion_path),
            ("statistics.manifest.json", statistics_manifest_path), ("corpus.manifest.json", corpus_manifest_path),
        ):
            atomic_write_bytes(staging / filename, path.read_bytes())
        atomic_write_bytes(staging / "decisions.csv", decisions[list(DECISION_COLUMNS)].to_csv(index=False, lineterminator="\n").encode("utf-8"))
        atomic_write_bytes(staging / "audit.json", (json.dumps(audit, indent=2) + "\n").encode("utf-8"))
        bundle_manifest = {
            "manifest_schema_version": 1,
            "rule_version": RULE_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "artifact_policy": "append_only_hash_verified; publish manifest hash in a versioned release; not filesystem write protection",
            "implementation_sha256": sha256_file(Path(__file__)),
            "verified_corpora": [{"path": str(path), "sha256": checked[path.name]} for path in (source_path, retained_path)],
            "files": [{"name": filename, "sha256": sha256_file(staging / filename)} for filename in BUNDLE_FILES],
            "limitations": ["interacting_authors cannot be recomputed from messages with a verified historical predicate", "manual exclusion reasons are not available per channel", "552/3 exploratory thresholds and final 500 AND 5 thresholds have no recovered calibration rationale"],
        }
        atomic_write_bytes(staging / "manifest.json", (json.dumps(bundle_manifest, indent=2) + "\n").encode())
        staging.rename(output)
    return audit


def verify_historical_selection(bundle_dir: str | Path) -> dict:
    directory = Path(bundle_dir)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("rule_version") != RULE_VERSION:
        raise ValueError("unsupported historical selection rule")
    if {item["name"] for item in manifest["files"]} != set(BUNDLE_FILES):
        raise ValueError("unexpected historical bundle files")
    for item in manifest["files"]:
        _check_hash(directory / item["name"], item["sha256"])
    decisions = channel_decisions(pd.read_parquet(directory / "statistics.parquet"), _read_names(directory / "exclusions.txt"))
    recorded = pd.read_csv(directory / "decisions.csv", dtype={"guild_id": "string", "channel_id": "string"}, keep_default_na=False)
    try:
        pd.testing.assert_frame_equal(recorded, decisions[list(DECISION_COLUMNS)], check_dtype=False)
    except AssertionError as error:
        raise ValueError("recorded decisions differ from historical rule replay") from error
    audit = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
    if audit["counts"] != _counts(decisions):
        raise ValueError("bundle audit counts disagree with replay")
    return audit


def main() -> None:
    from discord_filtering.remove_channel import DATA_DIR, EXCLUSION_PATH, MESSAGES_PATH, OUTPUT_PATH, STATISTICS_PATH

    parser = argparse.ArgumentParser(description="Freeze or replay historical channel decisions without redefining interacting_authors.")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--statistics", type=Path, default=STATISTICS_PATH)
    freeze.add_argument("--exclusions", type=Path, default=EXCLUSION_PATH)
    freeze.add_argument("--source", type=Path, default=MESSAGES_PATH)
    freeze.add_argument("--retained", type=Path, default=OUTPUT_PATH)
    freeze.add_argument("--output", type=Path, default=DATA_DIR.parents[4] / "annotations/channel_selection_2026-10-07")
    verify = commands.add_parser("verify")
    verify.add_argument("bundle", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "freeze":
        result = freeze_historical_selection(arguments.statistics, arguments.exclusions, arguments.source, arguments.retained, arguments.output)
    else:
        result = verify_historical_selection(arguments.bundle)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()