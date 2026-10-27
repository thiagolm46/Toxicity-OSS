"""Reproducible sampling-design diagnostics; never filter or redraw a sample."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from discord_disentanglement.population_report import distribution, markdown_table, number, percentage
from discord_disentanglement.sampling import CHANNEL_KEY, DEFAULT_SAMPLE, INCLUDED_STATUSES, PERIOD_KEY, ROOT, select_hierarchical_windows
from discord_filtering.storage import atomic_write_bytes, sha256_file


DEFAULT_AUDIT = ROOT / "data/processed/disentanglement/sampling_design_audit_v3"
DEFAULT_REPORT = ROOT / "docs/methodology/SAMPLING_DESIGN_AUDIT.md"


def inclusion_frame(channels: pd.DataFrame, candidates: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """Independently reconstruct inclusion probabilities for all eligible blocks."""
    available = candidates[CHANNEL_KEY].drop_duplicates()
    eligible = channels.loc[channels.eligibility_status.isin(INCLUDED_STATUSES)].merge(
        available, on=CHANNEL_KEY, validate="one_to_one",
    )
    eligible["channels_in_stratum"] = eligible.groupby(["guild_id", "size_stratum"])["channel_id"].transform("size")
    eligible["channels_drawn"] = eligible["channels_in_stratum"].clip(upper=parameters["channels_per_stratum"])
    eligible["channel_probability"] = eligible.channels_drawn / eligible.channels_in_stratum
    blocks = candidates.merge(eligible[[*CHANNEL_KEY, "size_stratum", "channels_in_stratum", "channels_drawn", "channel_probability"]], on=CHANNEL_KEY, validate="many_to_one")
    blocks["periods_in_channel"] = blocks.groupby(CHANNEL_KEY)["period"].transform("nunique")
    blocks["periods_drawn"] = blocks.periods_in_channel.clip(upper=parameters["periods_per_channel"])
    blocks["period_probability"] = blocks.periods_drawn / blocks.periods_in_channel
    blocks["windows_in_period"] = blocks.groupby(PERIOD_KEY)["window_index"].transform("size")
    blocks["windows_drawn"] = blocks.windows_in_period.clip(upper=parameters["windows_per_period"])
    blocks["window_probability"] = blocks.windows_drawn / blocks.windows_in_period
    blocks["inclusion_probability"] = blocks.channel_probability * blocks.period_probability * blocks.window_probability
    blocks["design_weight"] = 1 / blocks.inclusion_probability
    return blocks


def check_selection(
    channels: pd.DataFrame, candidates: pd.DataFrame, selected_channels: pd.DataFrame,
    selected_periods: pd.DataFrame, windows: pd.DataFrame, parameters: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected = inclusion_frame(channels, candidates, parameters)
    checks = []

    def record(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    keys = [*PERIOD_KEY, "window_index"]
    record("candidate_keys_unique", not candidates.duplicated(keys).any())
    record("selected_keys_unique", not windows.duplicated(keys).any())
    record("positive_eligible_probabilities", bool(expected.inclusion_probability.between(0, 1, inclusive="right").all()))
    record("channel_register_preserved", set(map(tuple, channels[CHANNEL_KEY].values)) == set(map(tuple, selected_channels[CHANNEL_KEY].values)))
    channel_expected = expected[[*CHANNEL_KEY, "channels_in_stratum", "channels_drawn", "channel_probability"]].drop_duplicates()
    joined_channels = selected_channels.merge(channel_expected, on=CHANNEL_KEY, how="left", suffixes=("_recorded", "_expected"), validate="one_to_one")
    for field in ("channels_in_stratum", "channels_drawn", "channel_probability"):
        wanted = joined_channels[f"{field}_expected"].fillna(0)
        record(field, bool(np.isclose(joined_channels[f"{field}_recorded"], wanted).all()))
    eligible_selected = joined_channels.loc[joined_channels.selected]
    record("only_eligible_channels_selected", bool(eligible_selected.channel_probability_expected.notna().all()))
    channel_quotas = expected[[*CHANNEL_KEY, "size_stratum", "channels_drawn"]].drop_duplicates().groupby(["guild_id", "size_stratum"]).channels_drawn.first()
    actual_quotas = selected_channels.loc[selected_channels.selected].groupby(["guild_id", "size_stratum"]).size()
    record("channel_quotas", bool(actual_quotas.reindex(channel_quotas.index, fill_value=0).eq(channel_quotas).all()))
    expected_periods = expected.loc[expected.set_index(CHANNEL_KEY).index.isin(eligible_selected.set_index(CHANNEL_KEY).index)]
    expected_periods = expected_periods[[*PERIOD_KEY, "periods_in_channel", "periods_drawn", "period_probability", "windows_in_period", "windows_drawn"]].drop_duplicates()
    record("period_register_complete", set(map(tuple, expected_periods[PERIOD_KEY].values)) == set(map(tuple, selected_periods[PERIOD_KEY].values)))
    compared_periods = selected_periods.merge(expected_periods, on=PERIOD_KEY, suffixes=("_recorded", "_expected"), how="left", validate="one_to_one")
    for field in ("periods_in_channel", "periods_drawn", "period_probability", "windows_in_period", "windows_drawn"):
        record(field, bool(np.isclose(compared_periods[f"{field}_recorded"], compared_periods[f"{field}_expected"]).all()))
    actual_periods = selected_periods.loc[selected_periods.selected].groupby(CHANNEL_KEY).size()
    wanted_periods = expected_periods.groupby(CHANNEL_KEY).periods_drawn.first()
    record("period_quotas", bool(actual_periods.reindex(wanted_periods.index, fill_value=0).eq(wanted_periods).all()))
    selected_period_keys = set(map(tuple, selected_periods.loc[selected_periods.selected, PERIOD_KEY].values))
    record("only_selected_periods_have_windows", set(map(tuple, windows[PERIOD_KEY].values)) == selected_period_keys)
    actual_windows = windows.groupby(PERIOD_KEY).size()
    wanted_windows = selected_periods.loc[selected_periods.selected].set_index(PERIOD_KEY).windows_drawn
    record("window_quotas", bool(actual_windows.reindex(wanted_windows.index, fill_value=0).eq(wanted_windows).all()))
    compared = windows.merge(expected, on=keys, suffixes=("_recorded", "_expected"), how="left", validate="one_to_one")
    for field in ("channel_probability", "period_probability", "window_probability", "inclusion_probability", "design_weight", "annotated_message_count", "first_position", "last_position"):
        record(field + "_per_window", bool(np.isclose(compared[f"{field}_recorded"], compared[f"{field}_expected"]).all()))
    ordered = candidates.sort_values([*PERIOD_KEY, "window_index"])
    previous = ordered.groupby(PERIOD_KEY).last_position.shift()
    record("candidate_spans_do_not_overlap", bool((previous.isna() | (ordered.first_position > previous)).all()))
    record("candidate_target_counts", bool(ordered.annotated_message_count.between(1, parameters["target_messages"]).all()))
    last_index = ordered.groupby(PERIOD_KEY).window_index.transform("max")
    record("only_final_blocks_can_be_short", bool(ordered.loc[ordered.window_index != last_index, "annotated_message_count"].eq(parameters["target_messages"]).all()))
    return pd.DataFrame(checks), expected


def window_diagnostics(messages: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for annotation_id, group in messages.groupby("annotation_id", sort=True):
        group = group.sort_values("position").reset_index(drop=True)
        targets = group.loc[~group.is_context]
        times = pd.to_datetime(group.timestamp, utc=True, format="ISO8601")
        target_times = pd.to_datetime(targets.timestamp, utc=True, format="ISO8601")
        gaps = target_times.diff().dt.total_seconds().dropna()
        locations = {str(row.message_id).strip(): index for index, row in enumerate(group.itertuples(index=False))}
        edges = []
        target_edges = []
        for index, message in enumerate(group.itertuples(index=False)):
            parent = _text(message.referenced_message_id)
            parent_guild = _text(getattr(message, "referenced_guild_id", None)) or _text(message.guild_id)
            if message.message_type != 19 or parent not in locations or parent_guild != _text(message.guild_id):
                continue
            parent_index = locations[parent]
            if parent_index >= index:
                continue
            edges.append((parent_index, index))
            if not message.is_context:
                target_edges.append((parent_index, index))
        overlapping_components = 0
        component_count = 0
        if edges:
            edge_array = np.asarray(edges)
            graph = csr_matrix((np.ones(len(edges)), (edge_array[:, 0], edge_array[:, 1])), shape=(len(group), len(group)))
            _, labels = connected_components(graph, directed=False)
            touched = {int(labels[child]) for _, child in target_edges}
            spans = []
            for component in touched:
                members = np.flatnonzero(labels == component)
                spans.append((int(members.min()), int(members.max())))
            component_count = len(spans)
            for first, (start, end) in enumerate(spans):
                for other_start, other_end in spans[first + 1:]:
                    overlapping_components += int(start < other_start < end or other_start < start < other_end)
        crossings = sum(
            int(start < other_start < end < other_end or other_start < start < other_end < end)
            for index, (start, end) in enumerate(target_edges)
            for other_start, other_end in target_edges[index + 1:]
        )
        author_counts = targets.author_id.value_counts()
        native_sources = targets.message_type.eq(19) & targets.referenced_message_id.map(_text).notna()
        rows.append({
            "annotation_id": annotation_id, "guild_id": str(group.guild_id.iloc[0]), "channel_id": str(group.channel_id.iloc[0]),
            "target_count": len(targets), "context_count": int(group.is_context.sum()), "visible_count": len(group),
            "preceding_context_count": int(group.position.lt(targets.position.min()).sum()),
            "target_duration_hours": (target_times.max() - target_times.min()).total_seconds() / 3600,
            "visible_duration_hours": (times.max() - times.min()).total_seconds() / 3600,
            "median_target_gap_hours": gaps.median() / 3600 if len(gaps) else np.nan,
            "max_target_gap_hours": gaps.max() / 3600 if len(gaps) else np.nan,
            "distinct_target_authors": len(author_counts),
            "largest_target_author_share": author_counts.max() / len(targets),
            "target_author_transition_ratio": float(targets.author_id.ne(targets.author_id.shift()).iloc[1:].mean()) if len(targets) > 1 else np.nan,
            "native_reply_target_sources": int(native_sources.sum()),
            "visible_native_target_edges": len(target_edges),
            "native_components_touching_targets": component_count,
            "overlapping_native_component_pairs": overlapping_components,
            "crossing_native_target_edge_pairs": crossings,
        })
    return pd.DataFrame(rows).merge(windows[["annotation_id", "size_stratum", "period", "inclusion_probability", "design_weight"]], on="annotation_id", validate="one_to_one")


def native_reply_diagnostics(
    messages: pd.DataFrame, windows: pd.DataFrame, source: Path, *, memory_limit: str = "2GB",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    targets = messages.loc[~messages.is_context].copy()
    targets = targets.loc[targets.message_type.eq(19) & targets.referenced_message_id.map(_text).notna()]
    references = pd.DataFrame({
        "annotation_id": targets.annotation_id,
        "guild_id": targets.guild_id.map(_text), "channel_id": targets.channel_id.map(_text),
        "source_message_id": targets.message_id.map(_text), "source_position": targets.position,
        "parent_id": targets.referenced_message_id.map(_text),
        "parent_guild_id": targets.get("referenced_guild_id", pd.Series(index=targets.index, dtype=object)).map(_text).fillna(targets.guild_id.map(_text)),
    }).reset_index(drop=True)
    with tempfile.TemporaryDirectory(prefix="sampling-audit-") as temporary:
        with duckdb.connect(str(Path(temporary) / "audit.duckdb")) as connection:
            connection.execute("SET memory_limit = ?", [memory_limit])
            connection.execute("SET TimeZone = 'UTC'")
            connection.execute("SET temp_directory = ?", [temporary])
            connection.execute("SET threads = 2")
            connection.execute("SET preserve_insertion_order = false")
            connection.from_parquet(str(source)).create_view("source")
            connection.execute("""
                CREATE TABLE raw AS
                WITH normalized AS (
                    SELECT nullif(trim(cast(guild_id AS VARCHAR)), '') AS guild_id,
                           nullif(trim(cast(channel_id AS VARCHAR)), '') AS channel_id,
                           nullif(trim(cast(message_id AS VARCHAR)), '') AS message_id,
                           nullif(trim(cast(author_id AS VARCHAR)), '') AS author_id,
                           try_cast(timestamp AS TIMESTAMPTZ) AS sent_at,
                           coalesce(is_bot = false AND (
                               nullif(trim(content), '') IS NOT NULL OR
                               coalesce(attachment_count, 0) + coalesce(embed_count, 0) + coalesce(sticker_count, 0) > 0
                           ), false) AS usable
                    FROM source
                )
                SELECT *, count(*) OVER (PARTITION BY guild_id, message_id) AS copies FROM normalized
            """)
            connection.execute("""
                CREATE TABLE ordered AS
                SELECT *, row_number() OVER (PARTITION BY guild_id, channel_id ORDER BY sent_at, message_id) AS position
                FROM raw WHERE guild_id IS NOT NULL AND channel_id IS NOT NULL
                    AND message_id IS NOT NULL AND author_id IS NOT NULL AND sent_at IS NOT NULL AND copies = 1
            """)
            technical = connection.execute("""
                SELECT guild_id, channel_id, count(*) AS valid_records,
                       count(*) FILTER (WHERE usable) AS technical_targets
                FROM ordered GROUP BY guild_id, channel_id
            """).fetchdf()
            connection.register("refs", references)
            resolved = connection.execute("""
                WITH parents AS (
                    SELECT guild_id, message_id, count(*) AS copies,
                           min(channel_id) AS channel_id, min(sent_at) AS sent_at, min(author_id) AS author_id
                    FROM raw GROUP BY guild_id, message_id
                )
                SELECT refs.*, parent.copies AS parent_copies, parent.channel_id AS parent_channel_id,
                       parent.sent_at AS parent_timestamp, parent.author_id AS parent_author_id,
                       ordered.position AS parent_position
                FROM refs LEFT JOIN parents parent ON parent.guild_id = refs.parent_guild_id AND parent.message_id = refs.parent_id
                LEFT JOIN ordered ON ordered.guild_id = refs.parent_guild_id AND ordered.message_id = refs.parent_id
                ORDER BY refs.annotation_id, refs.source_position
            """).fetchdf()
    starts = windows.set_index("annotation_id").first_position.to_dict()
    visible = {
        annotation_id: {_text(value) for value in group.message_id}
        for annotation_id, group in messages.groupby("annotation_id")
    }
    statuses = []
    for reply in resolved.itertuples(index=False):
        if pd.isna(reply.parent_copies):
            status = "parent_not_in_corpus"
        elif reply.parent_copies != 1:
            status = "ambiguous_duplicate_parent"
        elif reply.parent_guild_id != reply.guild_id or reply.parent_channel_id != reply.channel_id:
            status = "different_channel_or_server"
        elif pd.isna(reply.parent_position):
            status = "parent_structurally_unavailable"
        elif reply.parent_position >= reply.source_position:
            status = "not_preceding"
        elif reply.parent_id in visible[reply.annotation_id]:
            status = "visible"
        elif reply.parent_position < starts[reply.annotation_id]:
            status = "before_visible_context"
        else:
            status = "unexpected_missing_visible_parent"
        statuses.append(status)
    resolved["status"] = statuses
    resolved["required_preceding_records"] = (resolved.annotation_id.map(starts) - resolved.parent_position).clip(lower=0)
    return resolved, technical


def context_sensitivity(replies: pd.DataFrame, budgets: list[int]) -> pd.DataFrame:
    resolved = replies.loc[replies.status.isin(["visible", "before_visible_context", "unexpected_missing_visible_parent"])]
    rows = []
    for budget in sorted(set(budgets)):
        visible = int(resolved.required_preceding_records.le(budget).sum())
        rows.append({"preceding_records": budget, "native_target_references": len(replies),
                     "resolved_same_channel_preceding": len(resolved), "visible_references": visible,
                     "coverage_of_resolved": visible / len(resolved) if len(resolved) else np.nan})
    return pd.DataFrame(rows)


def allocation_diagnostics(expected: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, keys in (("server", ["guild_id"]), ("size", ["size_stratum"]), ("month", ["period"]), ("channel", CHANNEL_KEY)):
        for unit, population in expected.groupby(keys, sort=True):
            values = unit if isinstance(unit, tuple) else (unit,)
            selected = windows
            for key, value in zip(keys, values):
                selected = selected.loc[selected[key] == value]
            rows.append({
                "scope": scope, "unit": "/".join(map(str, values)),
                "candidate_windows": len(population), "population_targets": int(population.annotated_message_count.sum()),
                "expected_windows": population.inclusion_probability.sum(),
                "actual_windows": len(selected),
                "expected_targets": (population.inclusion_probability * population.annotated_message_count).sum(),
                "actual_targets": int(selected.annotated_message_count.sum()),
                "ht_target_total": (selected.design_weight * selected.annotated_message_count).sum(),
            })
    return pd.DataFrame(rows)


def stratum_diagnostics(channels: pd.DataFrame, expected: pd.DataFrame) -> pd.DataFrame:
    eligible = channels.merge(expected[CHANNEL_KEY].drop_duplicates(), on=CHANNEL_KEY, validate="one_to_one")
    rows = []
    for (guild_id, size), group in eligible.groupby(["guild_id", "size_stratum"], sort=True):
        blocks = expected.loc[(expected.guild_id == guild_id) & (expected.size_stratum == size)]
        volumes = group.usable_human_messages
        rows.append({
            "guild_id": guild_id, "size_stratum": size, "population_channels": len(group),
            "drawn_channels": int(blocks.channels_drawn.iloc[0]),
            "channel_probability": float(blocks.channel_probability.iloc[0]),
            "certainty_stratum": blocks.channels_drawn.iloc[0] == len(group),
            "min_usable_volume": int(volumes.min()), "median_usable_volume": float(volumes.median()),
            "max_usable_volume": int(volumes.max()),
            "within_stratum_volume_cv": float(volumes.std(ddof=0) / volumes.mean()) if volumes.mean() else 0.0,
            "expected_windows": float(blocks.inclusion_probability.sum()),
            "expected_targets": float((blocks.inclusion_probability * blocks.annotated_message_count).sum()),
        })
    return pd.DataFrame(rows)


def known_total_variance(expected: pd.DataFrame, value_field: str, *, expanded: bool) -> dict:
    """Exact design moments for a known block total, not variance from labels."""
    def aggregate(units: pd.DataFrame, drawn: int, stage: str) -> dict:
        population = len(units)
        fraction = drawn / population
        factor = 1 / fraction if expanded else 1.0
        between = drawn * (1 - fraction) * units["mean"].var(ddof=1) if population > 1 else 0.0
        result = {"mean": float(factor * fraction * units["mean"].sum())}
        for component in ("channel", "period", "window"):
            result[component] = float(factor ** 2 * fraction * units[component].sum())
        result[stage] += float(factor ** 2 * between)
        return result

    period_rows = []
    for keys, group in expected.groupby(PERIOD_KEY, sort=True):
        units = pd.DataFrame({"mean": group[value_field].astype(float), "channel": 0.0, "period": 0.0, "window": 0.0})
        period_rows.append({**dict(zip(PERIOD_KEY, keys)), "size_stratum": group.size_stratum.iloc[0],
                            "periods_drawn": int(group.periods_drawn.iloc[0]), "channels_drawn": int(group.channels_drawn.iloc[0]),
                            **aggregate(units, int(group.windows_drawn.iloc[0]), "window")})
    channel_rows = []
    for keys, group in pd.DataFrame(period_rows).groupby(CHANNEL_KEY, sort=True):
        channel_rows.append({**dict(zip(CHANNEL_KEY, keys)), "size_stratum": group.size_stratum.iloc[0],
                             "channels_drawn": int(group.channels_drawn.iloc[0]),
                             **aggregate(group, int(group.periods_drawn.iloc[0]), "period")})
    strata = []
    for _, group in pd.DataFrame(channel_rows).groupby(["guild_id", "size_stratum"], sort=True):
        strata.append(aggregate(group, int(group.channels_drawn.iloc[0]), "channel"))
    totals = pd.DataFrame(strata).sum()
    variance = float(totals[["channel", "period", "window"]].sum())
    return {"mean": float(totals["mean"]), "variance": variance, "standard_deviation": float(np.sqrt(variance)),
            **{f"{stage}_variance": float(totals[stage]) for stage in ("channel", "period", "window")}}


def stratum_sensitivity(channels: pd.DataFrame, candidates: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    eligible = channels.loc[channels.eligibility_status.isin(INCLUDED_STATUSES)]
    quantiles = eligible.usable_human_messages.quantile([1 / 3, 2 / 3]).tolist()
    small_max = float(channels.small_max.iloc[0]) if "small_max" in channels else 1000.0
    medium_max = float(channels.medium_max.iloc[0]) if "medium_max" in channels else 10000.0
    strategies = [("frozen", small_max, medium_max), ("half_cutpoints", small_max / 2, medium_max / 2),
                  ("double_cutpoints", small_max * 2, medium_max * 2), ("volume_tertiles", *quantiles)]
    rows = []
    for label, lower, upper in strategies:
        frame = channels.copy()
        if label != "frozen":
            frame["size_stratum"] = np.where(frame.usable_human_messages <= lower, "small", np.where(frame.usable_human_messages <= upper, "medium", "large"))
        expected = inclusion_frame(frame, candidates, parameters)
        strata = stratum_diagnostics(frame, expected)
        short = expected.annotated_message_count < parameters["target_messages"]
        known_moments = known_total_variance(expected, "annotated_message_count", expanded=True)
        rows.append({
            "scenario": label, "small_max": lower, "medium_max": upper,
            "nonempty_strata": len(strata), "certainty_strata": int(strata.certainty_stratum.sum()),
            "planned_channels": int(strata.drawn_channels.sum()),
            "expected_windows": float(expected.inclusion_probability.sum()),
            "expected_targets": float((expected.inclusion_probability * expected.annotated_message_count).sum()),
            "expected_short_window_share": float(expected.loc[short, "inclusion_probability"].sum() / expected.inclusion_probability.sum()),
            "channel_weighted_within_stratum_volume_cv": float(np.average(strata.within_stratum_volume_cv, weights=strata.population_channels)),
            "known_target_total_relative_design_sd": known_moments["standard_deviation"] / known_moments["mean"],
        })
    return pd.DataFrame(rows)


def audit_sample(
    sample_dir: str | Path = DEFAULT_SAMPLE, output_dir: str | Path = DEFAULT_AUDIT,
    report_path: str | Path = DEFAULT_REPORT, *, memory_limit: str = "2GB", overwrite_report: bool = False,
) -> dict:
    sample = Path(sample_dir).resolve()
    output = Path(output_dir).resolve()
    report = Path(report_path).resolve()
    if output.exists():
        raise FileExistsError(f"use a new audit directory: {output}")
    if report.exists() and not overwrite_report:
        raise FileExistsError(f"report exists: {report}; use --overwrite-report")
    manifest = json.loads((sample / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected_hash in manifest["outputs"].items():
        if sha256_file(sample / filename) != expected_hash:
            raise ValueError(f"artifact hash mismatch: {filename}")
    source = Path(manifest["input_path"])
    if sha256_file(source) != manifest["input_sha256"]:
        raise ValueError("source hash mismatch")
    if sha256_file(sample / "channel_frame.csv") != manifest["frame_sha256"]:
        raise ValueError("frozen channel register hash mismatch")
    parameters = manifest["parameters"]
    ids = {"guild_id": str, "channel_id": str}
    channels = pd.read_csv(sample / "channel_frame.csv", dtype=ids, keep_default_na=False)
    candidates = pd.read_csv(sample / "window_frame.csv", dtype=ids)
    selected_channels = pd.read_csv(sample / "channel_selection.csv", dtype=ids)
    selected_periods = pd.read_csv(sample / "period_selection.csv", dtype=ids)
    windows = pd.read_csv(sample / "selected_windows.csv", dtype=ids)
    messages = pd.read_parquet(sample / "sampled_messages.parquet")
    checks, expected = check_selection(channels, candidates, selected_channels, selected_periods, windows, parameters)
    additions = []

    def record(name: str, passed: bool, detail: str = "") -> None:
        additions.append({"check": name, "passed": bool(passed), "detail": detail})

    replayed = select_hierarchical_windows(channels, candidates, **{
        key: parameters[key] for key in ("seed", "channels_per_stratum", "periods_per_channel", "windows_per_period")
    })[2]
    keys = [*PERIOD_KEY, "window_index"]
    record("seed_replay", set(map(tuple, windows[keys].values)) == set(map(tuple, replayed[keys].values)))
    targets = messages.loc[~messages.is_context]
    record("target_memberships_unique", not targets.duplicated(["guild_id", "message_id"]).any())
    record("target_membership_counts", targets.groupby("annotation_id").size().reindex(windows.annotation_id).to_numpy().tolist() == windows.annotated_message_count.tolist())
    record("context_has_no_target_probability", bool(messages.loc[messages.is_context, "target_inclusion_probability"].isna().all()))
    for source_field, window_field in (("target_inclusion_probability", "inclusion_probability"), ("target_design_weight", "design_weight")):
        joined = targets.merge(windows[["annotation_id", window_field]], on="annotation_id", validate="many_to_one")
        record(source_field, bool(np.isclose(joined[source_field], joined[window_field]).all()))
    metrics = window_diagnostics(messages, windows)
    replies, technical = native_reply_diagnostics(messages, windows, source, memory_limit=memory_limit)
    source_counts = technical.set_index(CHANNEL_KEY).technical_targets
    candidate_counts = candidates.groupby(CHANNEL_KEY).annotated_message_count.sum()
    all_keys = source_counts.index.union(candidate_counts.index)
    record("candidate_targets_match_source_census", bool(source_counts.reindex(all_keys, fill_value=0).eq(candidate_counts.reindex(all_keys, fill_value=0)).all()))
    record("no_unexpected_invisible_parent", not replies.status.eq("unexpected_missing_visible_parent").any())
    record("saved_implementation_matches_current_sampler", sha256_file(ROOT / "discord_disentanglement/sampling.py") == manifest["implementation_sha256"])
    checks = pd.concat([checks, pd.DataFrame(additions)], ignore_index=True)
    allocations = allocation_diagnostics(expected, windows)
    strata = stratum_diagnostics(channels, expected)
    sensitivity = stratum_sensitivity(channels, candidates, parameters)
    contexts = context_sensitivity(replies, [0, 50, 100, parameters["context_messages"], 400])
    distributions = []
    groups = [("all", metrics), ("full_blocks", metrics.loc[metrics.target_count == parameters["target_messages"]]),
              ("short_blocks", metrics.loc[metrics.target_count < parameters["target_messages"]])]
    groups.extend((str(size), group) for size, group in metrics.groupby("size_stratum"))
    for label, group in groups:
        for field in ("target_count", "target_duration_hours", "visible_duration_hours", "max_target_gap_hours", "distinct_target_authors", "largest_target_author_share", "context_count", "design_weight"):
            values = group[field].dropna()
            distributions.append({"group": label, "metric": field, "count": len(values),
                                  **{key: float(value) if len(values) else np.nan for key, value in zip(
                                      ("min", "p25", "median", "mean", "p75", "p90", "p95", "max"),
                                      (values.min(), values.quantile(.25), values.median(), values.mean(), values.quantile(.75), values.quantile(.9), values.quantile(.95), values.max()),
                                  )}})
    distribution_frame = pd.DataFrame(distributions)
    short = metrics.target_count < parameters["target_messages"]
    expected_short = expected.annotated_message_count < parameters["target_messages"]
    message_weights = targets.target_design_weight.to_numpy()
    current_context = contexts.loc[contexts.preceding_records == parameters["context_messages"]].iloc[0]
    singleton_noncertainty = selected_periods.selected & selected_periods.windows_drawn.eq(1) & selected_periods.windows_in_period.gt(1)
    expected["short_window"] = expected.annotated_message_count.lt(parameters["target_messages"]).astype(int)
    variance_rows = []
    for label, field, expanded, observed in (
        ("ht_target_total", "annotated_message_count", True, float((windows.design_weight * windows.annotated_message_count).sum())),
        ("unweighted_target_count", "annotated_message_count", False, len(targets)),
        ("short_window_count", "short_window", False, int(short.sum())),
    ):
        moments = known_total_variance(expected, field, expanded=expanded)
        variance_rows.append({"quantity": label, "observed": observed, **moments,
                              "standardized_deviation_not_p_value": (observed - moments["mean"]) / moments["standard_deviation"] if moments["standard_deviation"] else np.nan})
    variances = pd.DataFrame(variance_rows)
    summary = {
        "all_checks_passed": bool(checks.passed.all()), "checks": len(checks),
        "frame_channels": len(channels), "sampled_channels": int(selected_channels.selected.sum()),
        "sampled_servers": int(windows.guild_id.nunique()), "windows": len(windows), "target_messages": len(targets),
        "eligible_technical_targets": int(expected.annotated_message_count.sum()),
        "expected_windows": float(expected.inclusion_probability.sum()),
        "expected_targets": float((expected.inclusion_probability * expected.annotated_message_count).sum()),
        "actual_short_windows": int(short.sum()),
        "expected_short_windows": float(expected.loc[expected_short, "inclusion_probability"].sum()),
        "singleton_target_windows": int(metrics.target_count.eq(1).sum()),
        "windows_at_most_ten_targets": int(metrics.target_count.le(10).sum()),
        "windows_over_24_hours": int(metrics.target_duration_hours.gt(24).sum()),
        "windows_over_seven_days": int(metrics.target_duration_hours.gt(168).sum()),
        "windows_with_one_target_author": int(metrics.distinct_target_authors.eq(1).sum()),
        "windows_with_observed_component_interleaving": int(metrics.overlapping_native_component_pairs.gt(0).sum()),
        "windows_with_crossing_native_edges": int(metrics.crossing_native_target_edge_pairs.gt(0).sum()),
        "native_target_references": len(replies), "native_reference_statuses": replies.status.value_counts().to_dict(),
        "visible_native_references_at_current_context": int(current_context.visible_references),
        "resolved_native_references": int(current_context.resolved_same_channel_preceding),
        "noncertainty_periods_with_one_window": int(singleton_noncertainty.sum()),
        "kish_message_weight_ess_only": float(message_weights.sum() ** 2 / np.square(message_weights).sum()),
        "ht_target_total": float((windows.design_weight * windows.annotated_message_count).sum()),
        "certainty_channel_strata": int(strata.certainty_stratum.sum()), "channel_strata": len(strata),
        "ht_known_target_design_sd": float(variances.loc[variances.quantity == "ht_target_total", "standard_deviation"].item()),
        "ht_known_target_standardized_deviation": float(variances.loc[variances.quantity == "ht_target_total", "standardized_deviation_not_p_value"].item()) if variances.loc[variances.quantity == "ht_target_total", "standard_deviation"].item() else None,
    }
    tables = {
        "checks.csv": checks, "candidate_probabilities.csv": expected, "strata.csv": strata,
        "allocation.csv": allocations, "stratum_sensitivity.csv": sensitivity,
        "window_diagnostics.csv": metrics, "window_distribution.csv": distribution_frame,
        "native_reply_diagnostics.csv": replies, "context_sensitivity.csv": contexts,
        "source_technical_counts.csv": technical,
        "known_total_variance.csv": variances,
    }
    output.mkdir(parents=True)
    for filename, frame in tables.items():
        frame.to_csv(output / filename, index=False)
    atomic_write_bytes(output / "summary.json", (json.dumps(summary, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"))
    text = _render_report(summary, checks, allocations, sensitivity, metrics, contexts, variances, manifest, output)
    atomic_write_bytes(output / "report.md", text.encode("utf-8"))
    report.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(report, text.encode("utf-8"), overwrite=overwrite_report)
    filenames = [*tables, "summary.json", "report.md"]
    provenance = {
        "sample_path": str(sample), "sample_manifest_sha256": sha256_file(sample / "manifest.json"),
        "source_sha256_verified": manifest["input_sha256"], "implementation_sha256": sha256_file(Path(__file__)),
        "parameters": {"memory_limit": memory_limit}, "summary": summary,
        "report_path": str(report), "report_sha256": sha256_file(report),
        "outputs": {filename: sha256_file(output / filename) for filename in filenames},
        "limitations": ["native edges are sparse observed evidence, not semantic truth", "no windows filtered or replaced", "Kish ESS measures unequal weights only, not clustering", "sensitivity scenarios are not new samples or validated optima"],
    }
    atomic_write_bytes(output / "manifest.json", (json.dumps(provenance, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"))
    return summary


def _render_report(summary, checks, allocations, sensitivity, metrics, contexts, variances, manifest, output) -> str:
    lines = [
        "# Desenho amostral: auditoria do piloto", "",
        "Relatorio gerado por `python -m discord_disentanglement.sampling_audit`. Todos os calculos estao em `discord_disentanglement/sampling_audit.py`; os CSVs e hashes permitem conferir cada resultado. Nao houve alteracao da entrada, do cadastro ou do sorteio.", "",
        "## 1. Escopo e verificacao do mecanismo", "",
        "A inferencia e condicional aos servidores retidos e a elegibilidade provisoria. O mecanismo e estratificado no nivel dos canais (servidor x porte), com meses ativos e blocos sorteados nos niveis seguintes. Sortear meses nao e garantir cobertura de todos os segmentos temporais.", "",
        f"Resultado: **{int(checks.passed.sum())}/{len(checks)} verificacoes aprovadas**. Os hashes das entradas e do corpus foram verificados antes da analise. A semente foi reexecutada e as probabilidades recalculadas independentemente do registro do sorteio.", "",
        markdown_table(["Medida", "Valor"], [[key, number(summary[key], 2 if key.startswith("expected") else 0)] for key in (
            "frame_channels", "sampled_channels", "sampled_servers", "windows", "target_messages", "eligible_technical_targets", "expected_windows", "expected_targets",
        )]), "",
        "A formula pi = (n_h/N_h)(m_c/M_c)(w_ct/W_ct) e o peso 1/pi sao validos para cada bloco e suas mensagens-alvo. A ultima janela incompleta deve continuar no quadro para manter probabilidade positiva. O produto nao transforma a amostra em autoponderada: medias brutas de mensagens nao estimam automaticamente a media do corpus.", "",
        "A correspondencia entre os totais tecnicos do Parquet e os blocos tambem foi conferida. A estimativa Horvitz-Thompson do total observado na amostra nao precisa coincidir com o total conhecido em uma unica realizacao: essa diferenca nao e, isoladamente, erro de sorteio.", "",
        "Como todos os tamanhos dos blocos sao conhecidos, e possivel calcular a variancia EXATA sob este desenho para essas quantidades auxiliares, sem usar rotulos humanos. A lei da variancia total e aplicada recursivamente aos tres sorteios SRS sem reposicao, incluindo as correcoes de populacao finita. Isso nao estima a variancia de toxicidade, arestas semanticas ou desempenho de modelos.", "",
        markdown_table(["Quantidade auxiliar", "Observado", "Esperanca exata", "Desvio-padrao do desenho", "Desvio padronizado"], [
            [row.quantity, number(row.observed, 2), number(row.mean, 2), number(row.standard_deviation, 2), number(row.standardized_deviation_not_p_value, 3)]
            for row in variances.itertuples(index=False)
        ]), "",
        "O desvio padronizado e descritivo, nao um p-valor ou teste normal: a distribuicao do estimador pode ser assimetrica. Uma discrepancia grande do total HT conhecido e alerta de instabilidade dos pesos, nao prova isolada de vies. Os componentes exatos por nivel estao em `known_total_variance.csv`.", "",
        "A recursao para um sorteio de n entre N unidades com medias mu_i e variancias internas V_i usa Var(soma selecionada) = n(1-n/N) S_mu^2 + (n/N) soma V_i; para expansao HT, multiplica-se a media por N/n e a variancia por (N/n)^2. Estratos independentes sao somados.", "",
    ]
    failed = checks.loc[~checks.passed]
    if not failed.empty:
        lines.extend(["**Falhas a corrigir antes de aceitar a selecao:** " + ", ".join(failed.check), ""])
    lines.extend([
        "## 2. Estratos e distribuicao resultante", "",
        f"Ha {summary['channel_strata']} estratos nao vazios; {summary['certainty_channel_strata']} sao censitarios no nivel dos canais. Os limites de porte sao operacionais, nao um resultado validado como otimo. Estratos preservam cobertura e probabilidades conhecidas; homogeneidade do volume nao demonstra homogeneidade dos resultados de disentanglement.", "",
        "A tabela compara limites alternativos sem excluir canais nem refazer o sorteio. As cotas permanecem iguais, mas o custo esperado pode mudar. CV e apenas dispersao relativa do volume dentro de servidor x porte, nao variancia do estimador nem criterio suficiente para escolher cortes.", "",
        markdown_table(["Cenario", "Corte pequeno", "Corte medio", "Canais previstos", "Janelas esperadas", "Alvos esperados", "Fracao curta esperada", "CV de volume", "DP relativo HT auxiliar"], [
            [row.scenario, number(row.small_max, 1), number(row.medium_max, 1), number(row.planned_channels), number(row.expected_windows, 2), number(row.expected_targets, 2), percentage(row.expected_short_window_share, 1), number(row.channel_weighted_within_stratum_volume_cv, 3), percentage(row.known_target_total_relative_design_sd, 1)]
            for row in sensitivity.itertuples(index=False)
        ]), "",
        "Distribuicao por porte; esperado significa soma das probabilidades no quadro elegivel, nao uma cota exata de mensagens:", "",
        markdown_table(["Porte", "Alvos no quadro", "Janelas esperadas", "Janelas observadas", "Alvos esperados", "Alvos observados"], [
            [row.unit, number(row.population_targets), number(row.expected_windows, 2), number(row.actual_windows), number(row.expected_targets, 2), number(row.actual_targets)]
            for row in allocations.loc[allocations.scope == "size"].itertuples(index=False)
        ]), "",
        f"Foram observadas {summary['actual_short_windows']} janelas incompletas; o desenho previa {number(summary['expected_short_windows'], 2)} em media. Ha {summary['singleton_target_windows']} janelas com um alvo e {summary['windows_at_most_ten_targets']} com ate dez. Meses uniformes e blocos finais tornam janelas curtas especialmente provaveis em canais pouco ativos; isso nao constitui falha automaticamente.", "",
        "Distribuicoes completas por servidor, canal e mes estao em `allocation.csv`. A alocacao nao precisa reproduzir participacoes brutas do corpus: essa diferenca e intencional para evitar dominio dos maiores canais. Comparacoes aqui sao descritivas; proximidade ao valor esperado nao e teste de representatividade.", "",
        "## 3. Adequacao das janelas ao disentanglement", "",
        "Duracoes em horas; min/P25/mediana/media/P75/P90/P95/max. Mensagens singulares tem duracao zero, que nao demonstra troca rapida. Medidas abaixo descrevem somente a amostra realizada, nao estimativas ponderadas da populacao.", "",
        markdown_table(["Medida", "Min", "P25", "Mediana", "Media", "P75", "P90", "P95", "Max"], [
            [field, *distribution(metrics[field])] for field in (
                "target_count", "target_duration_hours", "visible_duration_hours", "max_target_gap_hours", "distinct_target_authors", "largest_target_author_share",
            )
        ]), "",
        "Comparacao dos dominios completos e incompletos, sem mudar sua elegibilidade:", "",
        markdown_table(["Dominio", "Janelas", "Mediana de alvos", "Duracao-alvo mediana (h)", "Mediana de autores-alvo", "Com proxy de entrelacamento"], [
            [label, len(group), number(group.target_count.median(), 1), number(group.target_duration_hours.median(), 2), number(group.distinct_target_authors.median(), 1), percentage(group.overlapping_native_component_pairs.gt(0).sum(), len(group))]
            for label, group in (("completo", metrics.loc[metrics.target_count.eq(manifest["parameters"]["target_messages"])]), ("incompleto", metrics.loc[metrics.target_count.lt(manifest["parameters"]["target_messages"])]))
        ]), "",
        f"{summary['windows_over_24_hours']} janelas-alvo duram mais de 24 horas e {summary['windows_over_seven_days']} mais de sete dias; {summary['windows_with_one_target_author']} possuem um unico autor-alvo. Sao indicadores para leitura humana, nao limiares de exclusao. Cortar por duracao ou numero de autores sem redefinir o estimando mudaria a populacao e poderia remover conversas esparsas legitimamente relevantes.", "",
        f"Ha sobreposicao de spans de componentes nativos distintos em {summary['windows_with_observed_component_interleaving']} janelas e arestas nativas cruzadas em {summary['windows_with_crossing_native_edges']}. Sao proxies observaveis de entrelacamento: componentes nativos podem fragmentar a mesma conversa semantica, e conversas reais podem nao usar replies explicitos. Ausencia do proxy nao comprova ausencia de conversas paralelas; sua presenca nao valida os rotulos semanticos.", "",
        "Os componentes sao calculados com arestas nativas anteriores e visiveis; contam-se somente componentes que recebem uma aresta de fonte-alvo. Sobreposicao significa spans cronologicos intercalados; cruzamento usa pos(pai1) < pos(pai2) < pos(filho1) < pos(filho2), ou simetrico. Multiplos autores ou alta atividade sozinhos nao comprovam entrelacamento.", "",
        "Uma janela operacional por contagem nao e necessariamente um episodio conversacional compacto: spans longos podem reunir trocas separadas por dias. A sobreposicao de arestas de longa duracao tambem nao comprova simultaneidade local. Portanto, nao se deve afirmar que todas as janelas sao casos uteis de entrelacamento apenas porque passaram nas restricoes tecnicas. A duracao e os silencios devem ser confrontados com leitura humana, preservando tambem casos esparsos e sem entrelacamento para avaliar a especificidade do benchmark.", "",
        "### Contexto e truncamento observavel", "",
        markdown_table(["Status de antecedente nativo", "Referencias de alvos"], [[status, number(count)] for status, count in sorted(summary["native_reference_statuses"].items())]), "",
        "A sensibilidade abaixo mantem as mesmas fontes-alvo e varia apenas o numero de registros anteriores visiveis. O denominador de cobertura e restrito a antecedentes resolvidos, anteriores, no mesmo canal e tecnicamente ordenaveis. Nao inclui referencias ausentes do corpus, duplicadas ou de outros canais como se fossem falha de contexto.", "",
        markdown_table(["Registros anteriores", "Referencias nativas", "Resolvidas elegiveis", "Visiveis", "Cobertura das resolvidas"], [
            [row.preceding_records, row.native_target_references, row.resolved_same_channel_preceding, row.visible_references, percentage(row.visible_references, row.resolved_same_channel_preceding)]
            for row in contexts.itertuples(index=False)
        ]), "",
        "Essa cobertura nao mede recuperacao de antecedentes semanticos desconhecidos nem determina automaticamente um contexto ideal. Aumentar contexto pode recuperar evidencia observada, mas tambem aumentar muito o custo e a duracao visivel em canais esparsos.", "",
        "## 4. Ajustes necessarios e decisoes pendentes", "",
        "1. **Correcoes do mecanismo:** corrigir qualquer verificacao reprovada antes de aceitar a amostra. Se todas passarem, nao ha evidencia nesta auditoria de erro de denominador, peso, cota, sobreposicao de alvos ou reproducao da semente.",
        "2. **Estimando e pesos:** declarar se o objetivo e benchmark com cobertura entre canais, media entre canais ou media entre mensagens. Preservar as tres probabilidades e nao substituir pesos por volume bruto. Separar avaliacao do benchmark de inferencia populacional.",
        f"3. **Incerteza:** {summary['noncertainty_periods_with_one_window']} meses sorteados tem uma unica janela observada apesar de multiplos blocos disponiveis. Nesse nivel nao ha replicacao para estimar diretamente a variancia dentro do mes sem suposicoes adicionais. Se intervalos design-based forem requisito, avaliar pelo menos duas janelas nos meses nao censitarios e rebalancear o orcamento antes de novo sorteio. Nao e necessario aumentar a amostra apenas para produzir um benchmark descritivo.",
        "4. **Estratos:** manter os cortes atuais como provisao auditavel; nao adotar novos cortes apenas por parecerem mais equilibrados em volume. Comparar custo, cobertura e variacao dos resultados anotados antes de alegar eficiencia superior.",
        "5. **Adequacao semantica:** usar o piloto humano para medir conversas simultaneas reais, antecedentes fora do contexto, ambiguidade e tempo de anotacao. Comparar blocos completos, caudas curtas e janelas de diferentes duracoes como dominios de analise, sem descarta-los antecipadamente.",
        "6. **Elegibilidade:** a decisao sobre canais paralelos ao desenvolvimento permanece com a revisao tematica. Nao introduzir filtros por reply, autores ou duracao para resolver uma decisao de escopo.", "",
        f"O tamanho de Kish calculado apenas pelos pesos das mensagens e {number(summary['kish_message_weight_ess_only'], 2)} para {summary['target_messages']} alvos. Nao e tamanho efetivo inferencial: ignora dependencia temporal, estratificacao e conglomerados. Bootstrap ingenuo de mensagens, ou de janelas sem respeitar os niveis do desenho, nao resolve a ausencia de replicacao.", "",
        "## 5. Reproducao e artefatos", "",
        "```powershell", "python -m discord_disentanglement.sampling_audit", "python -m pytest tests/test_sampling.py -q", "```", "",
        "A execucao recusa substituir a pasta de auditoria. Para repetir, use `--output <pasta_nova> --overwrite-report`; `--sample` permite auditar outro sorteio. `--report` permite escolher o documento gerado. Os artefatos incluem checks, probabilidades de todos os blocos, estratos, alocacao, sensibilidade dos cortes, diagnosticos de janelas, referencias nativas, sensibilidade de contexto, censo tecnico, resumo e manifesto.", "",
        f"Diretorio desta auditoria: `{output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}`. Semente do sorteio: `{manifest['parameters']['seed']}`. As distribuicoes por porte e por tamanho de bloco estao em `window_distribution.csv`; cada janela pode ser inspecionada por `annotation_id` em `window_diagnostics.csv` e nos artefatos originais.", "",
        "**Conclusao:** probabilidades corretas e utilidade semantica sao questoes distintas. O desenho pode ser executavel e probabilistico sem que todas as janelas mostrem entrelacamento. Esta auditoria nao certifica rotulos inexistentes e nao aplica novos filtros.", "",
    ])
    return "\n".join(lines)


def _text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value).strip() or None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit sampling design, inclusion probabilities, window usefulness and context; never redraw or filter.")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--memory-limit", default="2GB")
    parser.add_argument("--overwrite-report", action="store_true")
    arguments = parser.parse_args(argv)
    summary = audit_sample(arguments.sample, arguments.output, arguments.report,
                           memory_limit=arguments.memory_limit, overwrite_report=arguments.overwrite_report)
    print(json.dumps(summary, indent=2, ensure_ascii=True, allow_nan=False))
    if not summary["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()