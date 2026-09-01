from __future__ import annotations

import hashlib
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd

from discord_disentanglement.io import FIELD_ALIASES, load_discord_export, normalize_row
from discord_disentanglement.features import (
    cosine_similarity,
    question_score,
    response_marker_score,
    technical_tokens,
    tokenize,
)

from .config import ExperimentConfig


USER_MENTION_RE = re.compile(r"<@!?([A-Za-z0-9_]+)>")


@dataclass(slots=True)
class PreparedExperiment:
    messages: pd.DataFrame
    candidates: pd.DataFrame
    direct_reply_gold: pd.DataFrame
    candidate_fingerprint: str
    input_fingerprint: str
    split_summary: dict[str, Any]
    data_quality: dict[str, Any]
    prediction_columns: tuple[str, ...]


def load_experiment_messages(config: ExperimentConfig) -> pd.DataFrame:
    """Load the scoped, privacy-safe message table without generating candidates.

    This public reader is shared by the experiment preparation and the artifact-only
    inspection UI, preventing a second interpretation of aliases, anonymization or
    temporal split boundaries.
    """
    messages, _, _ = _load_messages(config)
    messages, _ = _assign_temporal_splits(messages, config)
    return messages


def prepare_experiment(config: ExperimentConfig) -> PreparedExperiment:
    messages, input_fingerprint, quality = _load_messages(config)
    quality["input_file_sha256"] = _sha256_file(config.input_path)
    messages, split_summary = _assign_temporal_splits(messages, config)
    vectors, token_sets, technical_sets = _build_train_fitted_tfidf(messages)
    candidates = _build_candidates(
        messages,
        vectors,
        token_sets,
        technical_sets,
        config,
    )
    gold, gold_quality = _extract_valid_direct_reply_gold(messages)
    quality.update(gold_quality)
    fingerprint = _candidate_fingerprint(candidates)
    return PreparedExperiment(
        messages=messages,
        candidates=candidates,
        direct_reply_gold=gold,
        candidate_fingerprint=fingerprint,
        input_fingerprint=input_fingerprint,
        split_summary=split_summary,
        data_quality=quality,
        prediction_columns=tuple(candidates.columns),
    )


def _load_messages(
    config: ExperimentConfig,
) -> tuple[pd.DataFrame, str, dict[str, Any]]:
    if not config.input_path.exists():
        raise FileNotFoundError(f"Entrada nao encontrada: {config.input_path}")
    rows, projection_quality = _load_projected_rows(config)
    if not rows:
        raise ValueError(
            f"Nenhuma mensagem encontrada para guild_id={config.guild_id!r} "
            f"guild_name={config.guild_name!r}"
        )

    normalized: list[dict[str, Any]] = []
    missing_message_ids = 0
    missing_channels = 0
    for row in rows:
        message_id = row.get("message_id")
        channel_id = row.get("channel_id")
        channel_name = row.get("channel_name")
        if not message_id:
            missing_message_ids += 1
            continue
        if not channel_id and not channel_name:
            missing_channels += 1
            continue
        content = str(row.get("content") or "")
        author_id = str(row.get("author_id") or f"UNKNOWN:{message_id}")
        reply_target = _reply_target_from_row(row)
        normalized.append(
            {
                "message_id": str(message_id),
                "guild_id": str(row.get("guild_id") or config.guild_id),
                "guild_name": row.get("guild_name"),
                "channel_id": str(channel_id) if channel_id else None,
                "channel_name": str(channel_name) if channel_name else None,
                "channel_key": (
                    f"id:{channel_id}"
                    if channel_id
                    else f"name:{str(channel_name).strip().casefold()}"
                ),
                "author_id_internal": author_id,
                "timestamp": pd.Timestamp(row["timestamp"]),
                "content_internal": content,
                "content_normalized": content,
                "content_mentions_internal": tuple(USER_MENTION_RE.findall(content)),
                "reply_target_internal": reply_target,
            }
        )
    if not normalized:
        raise ValueError("Todas as linhas foram rejeitadas por ID/canal ausente")

    dataframe = pd.DataFrame.from_records(normalized)
    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(dataframe["timestamp"].isna().sum())
    if invalid_timestamps:
        raise ValueError(
            f"Ha {invalid_timestamps} timestamp(s) invalidos; a execucao foi interrompida "
            "para preservar a reprodutibilidade temporal."
        )
    dataframe.sort_values(["timestamp", "message_id"], inplace=True, kind="stable")
    duplicate_ids = int(dataframe["message_id"].duplicated(keep="first").sum())
    dataframe.drop_duplicates("message_id", keep="first", inplace=True)
    dataframe.reset_index(drop=True, inplace=True)
    author_codes, _ = pd.factorize(dataframe["author_id_internal"], sort=False)
    dataframe["author_anon"] = [f"USER_{code + 1:05d}" for code in author_codes]
    dataframe["message_position"] = range(len(dataframe))
    input_fingerprint = _filtered_snapshot_fingerprint(dataframe)
    return dataframe, input_fingerprint, {
        **projection_quality,
        "input_rows_after_guild_filter": len(rows),
        "usable_unique_messages": int(len(dataframe)),
        "missing_message_id_rows_dropped": missing_message_ids,
        "missing_channel_rows_dropped": missing_channels,
        "duplicate_message_ids_dropped": duplicate_ids,
        "invalid_timestamps": invalid_timestamps,
    }


def _load_projected_rows(
    config: ExperimentConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read only the Neo4j row groups/columns when the source is Parquet."""

    suffix = config.input_path.suffix.lower()
    if suffix not in {".parquet", ".pq"}:
        if suffix == ".csv":
            with config.input_path.open("r", encoding="utf-8-sig", newline="") as handle:
                raw_rows = list(csv.DictReader(handle))
        elif suffix == ".json":
            raw_rows = _load_raw_json_rows(config.input_path)
        else:
            # Preserve the established error for unsupported formats.
            rows = load_discord_export(
                config.input_path,
                guild_id=config.guild_id,
                guild_name=config.guild_name,
            )
            return rows, {
                "input_read_mode": "format_loader_non_parquet",
                "parquet_filter_pushdown": False,
            }
        selected_raw = [row for row in raw_rows if _raw_row_matches_guild(row, config)]
        missing_timestamps = sum(
            _raw_timestamp_missing(row) for row in selected_raw
        )
        if missing_timestamps:
            raise ValueError(
                f"Ha {missing_timestamps} timestamp(s) ausentes no recorte Neo4j; "
                "nenhum horario de execucao sera inventado."
            )
        rows = [normalize_row(row) for row in selected_raw]
        return rows, {
            "input_read_mode": f"{suffix.removeprefix('.')}_validated_before_normalization",
            "parquet_filter_pushdown": False,
        }

    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pq.read_schema(config.input_path)
    available = set(schema.names)
    canonical_fields = (
        "message_id",
        "guild_id",
        "guild_name",
        "channel_id",
        "channel_name",
        "author_id",
        "timestamp",
        "content",
        "message_reference",
        "referenced_message",
        "reply_to_message_id",
    )
    projected_columns: list[str] = []
    for canonical in canonical_fields:
        for alias in FIELD_ALIASES[canonical]:
            if alias in available and alias not in projected_columns:
                projected_columns.append(alias)

    guild_column = next(
        (alias for alias in FIELD_ALIASES["guild_id"] if alias in available), None
    )
    if guild_column is None:
        raise ValueError(
            "Parquet sem coluna guild_id reconhecida: nao e seguro ler todo o corpus "
            "para localizar o servidor Neo4j."
        )
    guild_value: Any = config.guild_id
    guild_type = schema.field(guild_column).type
    if pa.types.is_integer(guild_type):
        guild_value = int(config.guild_id)
    filters: list[tuple[str, str, Any]] = [(guild_column, "==", guild_value)]
    if config.guild_name:
        guild_name_column = next(
            (alias for alias in FIELD_ALIASES["guild_name"] if alias in available),
            None,
        )
        if guild_name_column:
            filters.append((guild_name_column, "==", config.guild_name))

    raw_frame = pd.read_parquet(
        config.input_path,
        columns=projected_columns,
        filters=filters,
        engine="pyarrow",
    )
    timestamp_column = next(
        (alias for alias in FIELD_ALIASES["timestamp"] if alias in raw_frame.columns),
        None,
    )
    if timestamp_column is None:
        raise ValueError("Parquet sem coluna timestamp reconhecida")
    timestamp_values = raw_frame[timestamp_column]
    missing_timestamps = int(
        (timestamp_values.isna() | timestamp_values.astype(str).str.strip().eq("")).sum()
    )
    if missing_timestamps:
        raise ValueError(
            f"Ha {missing_timestamps} timestamp(s) ausentes no recorte Neo4j; "
            "nenhum horario de execucao sera inventado."
        )
    rows = [normalize_row(row) for row in raw_frame.to_dict(orient="records")]
    return rows, {
        "input_read_mode": "parquet_projected_with_filter_pushdown",
        "parquet_filter_pushdown": True,
        "projected_input_columns": projected_columns,
        "parquet_rows_after_pushdown": int(len(raw_frame)),
    }


def _load_raw_json_rows(path: Any) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("messages"), list):
        return [_inherit_json_context(row, payload) for row in payload["messages"] if isinstance(row, dict)]
    if isinstance(payload.get("channels"), list):
        rows: list[dict[str, Any]] = []
        for channel in payload["channels"]:
            if not isinstance(channel, dict) or not isinstance(channel.get("messages"), list):
                continue
            context = {**payload, **channel}
            rows.extend(
                _inherit_json_context(row, context)
                for row in channel["messages"]
                if isinstance(row, dict)
            )
        return rows
    return [payload]


def _inherit_json_context(row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    inherited = dict(row)
    for key in (
        "guild_id",
        "guildId",
        "guild_name",
        "guildName",
        "channel_id",
        "channelId",
        "channel_name",
        "channelName",
    ):
        if key not in inherited and key in context:
            inherited[key] = context[key]
    guild = context.get("guild")
    if isinstance(guild, dict):
        inherited.setdefault("guild_id", guild.get("id"))
        inherited.setdefault("guild_name", guild.get("name"))
    channel = context.get("channel")
    if isinstance(channel, dict):
        inherited.setdefault("channel_id", channel.get("id"))
        inherited.setdefault("channel_name", channel.get("name"))
    return inherited


def _raw_row_matches_guild(row: dict[str, Any], config: ExperimentConfig) -> bool:
    guild_id = _raw_alias_value(row, FIELD_ALIASES["guild_id"])
    guild_name = _raw_alias_value(row, FIELD_ALIASES["guild_name"])
    if config.guild_id and str(guild_id or "") != str(config.guild_id):
        return False
    if config.guild_name and str(guild_name or "").casefold() != config.guild_name.casefold():
        return False
    return True


def _raw_timestamp_missing(row: dict[str, Any]) -> bool:
    value = _raw_alias_value(row, FIELD_ALIASES["timestamp"])
    return value is None or str(value).strip() == ""


def _raw_alias_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] is not None and str(row[alias]).strip() != "":
            return row[alias]
        if "." not in alias:
            continue
        value: Any = row
        for part in alias.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None and str(value).strip() != "":
            return value
    return None


def _assign_temporal_splits(
    messages: pd.DataFrame,
    config: ExperimentConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    count = len(messages)
    if count < 5:
        raise ValueError("O protocolo temporal 60/20/20 requer ao menos cinco mensagens")
    train_end = max(1, int(count * config.train_fraction))
    validation_end = max(train_end + 1, int(count * (config.train_fraction + config.validation_fraction)))
    validation_end = min(validation_end, count - 1)
    split_values = ["train"] * train_end
    split_values.extend(["validation"] * (validation_end - train_end))
    split_values.extend(["test"] * (count - validation_end))
    result = messages.copy()
    result["split"] = split_values
    summary: dict[str, Any] = {
        "strategy": "global_chronological_message_order",
        "ratios": {"train": 0.60, "validation": 0.20, "test": 0.20},
        "counts": {
            split: int((result["split"] == split).sum())
            for split in ("train", "validation", "test")
        },
        "boundaries": {},
    }
    for split in ("train", "validation", "test"):
        split_rows = result[result["split"] == split]
        summary["boundaries"][split] = {
            "first_timestamp": _timestamp_text(split_rows["timestamp"].iloc[0]),
            "last_timestamp": _timestamp_text(split_rows["timestamp"].iloc[-1]),
        }
    return result, summary


def _build_train_fitted_tfidf(
    messages: pd.DataFrame,
) -> tuple[list[dict[str, float]], list[set[str]], list[set[str]]]:
    tokenized = [tokenize(text) for text in messages["content_normalized"].tolist()]
    train_positions = messages.index[messages["split"] == "train"].tolist()
    document_frequency: Counter[str] = Counter()
    for position in train_positions:
        document_frequency.update(set(tokenized[position]))
    train_count = max(1, len(train_positions))
    idf = {
        token: math.log((1 + train_count) / (1 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }
    unseen_idf = math.log(1 + train_count) + 1.0
    vectors: list[dict[str, float]] = []
    token_sets: list[set[str]] = []
    technical_sets: list[set[str]] = []
    for tokens in tokenized:
        counts = Counter(tokens)
        length = max(1, sum(counts.values()))
        vector = {
            token: (count / length) * idf.get(token, unseen_idf)
            for token, count in counts.items()
        }
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors.append({token: value / norm for token, value in vector.items()})
        token_set = set(tokens)
        token_sets.append(token_set)
        technical_sets.append(set(technical_tokens(tokens)))
    return vectors, token_sets, technical_sets


def _build_candidates(
    messages: pd.DataFrame,
    vectors: list[dict[str, float]],
    token_sets: list[set[str]],
    technical_sets: list[set[str]],
    config: ExperimentConfig,
) -> pd.DataFrame:
    columns: dict[str, list[Any]] = {
        "source_message_id": [],
        "target_message_id": [],
        "source_split": [],
        "channel_id": [],
        "channel_name": [],
        "target_channel_id": [],
        "target_channel_name": [],
        "source_timestamp": [],
        "target_timestamp": [],
        "delta_seconds": [],
        "message_distance": [],
        "candidate_generation_rank": [],
        "temporal_proximity": [],
        "semantic_similarity": [],
        "lexical_overlap": [],
        "source_mentions_target": [],
        "target_mentions_source": [],
        "adjacent_message": [],
        "author_turn": [],
        "same_author": [],
        "question_answer": [],
        "technical_overlap": [],
        "length_similarity": [],
        "recency_rank_score": [],
    }
    maximum_delta = config.max_time_delta_hours * 3600.0
    temporal_scale = min(maximum_delta, 2.0 * 3600.0)
    records = messages[
        [
            "message_id",
            "channel_id",
            "channel_name",
            "channel_key",
            "author_id_internal",
            "timestamp",
            "content_normalized",
            "content_mentions_internal",
            "split",
        ]
    ].to_dict(orient="records")

    # Only one channel group is resident in the ephemeral selection list at a time.
    for _, channel_group in messages.groupby("channel_key", sort=True):
        positions = channel_group.index.tolist()
        for local_source_position, source_position in enumerate(positions):
            if local_source_position == 0:
                continue
            source = records[source_position]
            eligible: list[tuple[int, float, int, float]] = []
            for lag, target_position in enumerate(
                reversed(positions[max(0, local_source_position - config.max_previous_messages) : local_source_position]),
                start=1,
            ):
                target = records[target_position]
                delta = float(
                    (source["timestamp"] - target["timestamp"]).total_seconds()
                )
                if delta <= 0.0:
                    continue
                if delta > maximum_delta:
                    break
                semantic = cosine_similarity(vectors[source_position], vectors[target_position])
                eligible.append((target_position, delta, lag, semantic))
            if not eligible:
                continue

            # A cap-independent interleaving makes each prefix K a real candidate
            # policy: odd ranks favor recency and even ranks favor topical strength.
            # Candidate Recall@K can therefore be interpreted without regenerating
            # candidates or consulting reply labels.
            selected: list[tuple[int, float, int, float]] = []
            selected_positions: set[int] = set()
            topical = sorted(
                eligible,
                key=lambda item: (-item[3], item[1], records[item[0]]["message_id"]),
            )
            recent_cursor = 0
            topical_cursor = 0
            while (
                len(selected) < config.max_candidates_per_message
                and len(selected_positions) < len(eligible)
            ):
                source_list = eligible if len(selected) % 2 == 0 else topical
                cursor = recent_cursor if source_list is eligible else topical_cursor
                while cursor < len(source_list) and source_list[cursor][0] in selected_positions:
                    cursor += 1
                if source_list is eligible:
                    recent_cursor = cursor + 1
                else:
                    topical_cursor = cursor + 1
                if cursor >= len(source_list):
                    source_list = topical if source_list is eligible else eligible
                    cursor = 0
                    while cursor < len(source_list) and source_list[cursor][0] in selected_positions:
                        cursor += 1
                    if cursor >= len(source_list):
                        break
                item = source_list[cursor]
                selected.append(item)
                selected_positions.add(item[0])

            for candidate_rank, (target_position, delta, lag, semantic) in enumerate(
                selected, start=1
            ):
                target = records[target_position]
                source_tokens = token_sets[source_position]
                target_tokens = token_sets[target_position]
                source_technical = technical_sets[source_position]
                target_technical = technical_sets[target_position]
                same_author = source["author_id_internal"] == target["author_id_internal"]
                source_mentions = set(source["content_mentions_internal"])
                target_mentions = set(target["content_mentions_internal"])
                _append_candidate(
                    columns,
                    source,
                    target,
                    delta=delta,
                    message_distance=float(source_position - target_position),
                    candidate_generation_rank=float(candidate_rank),
                    temporal_proximity=math.exp(-delta / temporal_scale),
                    semantic_similarity=semantic,
                    lexical_overlap=_jaccard(source_tokens, target_tokens),
                    source_mentions_target=float(
                        target["author_id_internal"] in source_mentions
                    ),
                    target_mentions_source=float(
                        source["author_id_internal"] in target_mentions
                    ),
                    adjacent_message=float(lag == 1),
                    author_turn=float(not same_author),
                    same_author=float(same_author),
                    question_answer=(
                        question_score(target["content_normalized"])
                        * max(
                            response_marker_score(source["content_normalized"]),
                            0.35 if len(source_tokens) >= 3 else 0.0,
                        )
                    ),
                    technical_overlap=_jaccard(source_technical, target_technical),
                    length_similarity=_length_similarity(source_tokens, target_tokens),
                    recency_rank_score=1.0 / lag,
                )
    candidates = pd.DataFrame(columns)
    numeric_columns = [
        "delta_seconds",
        "message_distance",
        "candidate_generation_rank",
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
    ]
    if not candidates.empty:
        candidates[numeric_columns] = candidates[numeric_columns].astype("float32")
        candidates[["message_distance", "candidate_generation_rank"]] = candidates[
            ["message_distance", "candidate_generation_rank"]
        ].astype("int32")
    return candidates


def _append_candidate(
    columns: dict[str, list[Any]],
    source: dict[str, Any],
    target: dict[str, Any],
    **features: float,
) -> None:
    columns["source_message_id"].append(source["message_id"])
    columns["target_message_id"].append(target["message_id"])
    columns["source_split"].append(source["split"])
    columns["channel_id"].append(source["channel_id"])
    columns["channel_name"].append(source["channel_name"])
    columns["target_channel_id"].append(target["channel_id"])
    columns["target_channel_name"].append(target["channel_name"])
    columns["source_timestamp"].append(source["timestamp"])
    columns["target_timestamp"].append(target["timestamp"])
    columns["delta_seconds"].append(features.pop("delta"))
    for feature_name, value in features.items():
        columns[feature_name].append(round(float(value), 8))


def _extract_valid_direct_reply_gold(
    messages: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    by_id = messages.set_index("message_id", drop=False)
    rows: list[dict[str, str]] = []
    raw_count = 0
    missing_target = 0
    cross_channel = 0
    non_past_target = 0
    for source in messages.itertuples(index=False):
        target_id = source.reply_target_internal
        if target_id is None or pd.isna(target_id) or not str(target_id).strip():
            continue
        target_id = str(target_id)
        raw_count += 1
        if target_id not in by_id.index:
            missing_target += 1
            continue
        target = by_id.loc[target_id]
        if source.channel_key != target["channel_key"]:
            cross_channel += 1
            continue
        if source.timestamp <= target["timestamp"]:
            non_past_target += 1
            continue
        rows.append(
            {
                "source_message_id": source.message_id,
                "target_message_id": str(target_id),
                "source_split": source.split,
            }
        )
    gold = pd.DataFrame.from_records(
        rows,
        columns=["source_message_id", "target_message_id", "source_split"],
    ).drop_duplicates("source_message_id", keep="first")
    return gold, {
        "direct_reply_references_raw": raw_count,
        "direct_reply_references_valid_same_channel_past": int(len(gold)),
        "direct_reply_target_missing_from_filtered_guild": missing_target,
        "direct_reply_cross_channel_excluded": cross_channel,
        "direct_reply_non_past_excluded": non_past_target,
    }


def _reply_target_from_row(row: dict[str, Any]) -> str | None:
    direct = row.get("reply_to_message_id")
    if direct is not None and not pd.isna(direct) and str(direct).strip():
        return str(direct)
    for field in ("message_reference", "referenced_message"):
        reference = row.get(field)
        if isinstance(reference, dict):
            for key in ("message_id", "messageId", "id"):
                if reference.get(key):
                    return str(reference[key])
    return None


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _length_similarity(left: set[str], right: set[str]) -> float:
    left_length = len(left)
    right_length = len(right)
    if left_length == 0 and right_length == 0:
        return 1.0
    if left_length == 0 or right_length == 0:
        return 0.0
    return min(left_length, right_length) / max(left_length, right_length)


def _candidate_fingerprint(candidates: pd.DataFrame) -> str:
    if candidates.empty:
        return hashlib.sha256(b"").hexdigest()
    hashes = pd.util.hash_pandas_object(
        candidates[["source_message_id", "target_message_id"]], index=False
    ).to_numpy()
    return hashlib.sha256(hashes.tobytes()).hexdigest()


def _filtered_snapshot_fingerprint(messages: pd.DataFrame) -> str:
    snapshot = messages[
        [
            "message_id",
            "channel_key",
            "author_id_internal",
            "timestamp",
            "content_internal",
            "reply_target_internal",
        ]
    ].copy()
    snapshot["reply_target_internal"] = snapshot["reply_target_internal"].fillna("")
    hashes = pd.util.hash_pandas_object(snapshot, index=False).to_numpy()
    return hashlib.sha256(hashes.tobytes()).hexdigest()


def _timestamp_text(value: Any) -> str:
    return pd.Timestamp(value).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Any) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
