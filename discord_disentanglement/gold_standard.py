from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from discord_disentanglement.io import load_discord_export


ANNOTATION_WINDOW_COLUMNS: tuple[str, ...] = (
    "annotation_id",
    "window_id",
    "guild_id",
    "guild_name",
    "channel_id",
    "channel_name",
    "context_start_message_id",
    "context_end_message_id",
    "first_annotated_message_id",
    "last_annotated_message_id",
    "context_start_timestamp",
    "context_end_timestamp",
    "annotation_start_timestamp",
    "annotation_end_timestamp",
    "context_message_count",
    "annotated_message_count",
    "total_message_count",
    "participant_count",
    "messages_json",
    "native_reply_edges_json",
    "native_reply_edges_visible_count",
    "native_reply_targets_outside_window_count",
    "native_reply_evidence_review",
    "human_reply_edges_json",
    "human_reply_source_statuses_json",
    "ambiguity",
    "annotator_id",
    "reviewed_at",
    "notes",
)


@dataclass(frozen=True, slots=True)
class GoldStandardArtifacts:
    filtered_messages_path: Path
    direct_reply_edges_path: Path
    annotation_windows_path: Path
    summary_path: Path


def export_native_reply_gold_standard(
    input_path: Path,
    output_dir: Path,
    *,
    guild_id: str | None = None,
    guild_name: str | None = None,
    channel_id: str | None = None,
    channel_name: str | None = None,
    annotated_window_size: int = 100,
    context_message_count: int = 200,
) -> GoldStandardArtifacts:
    """Export continuous per-channel windows for human conversation annotation."""
    if annotated_window_size < 1:
        raise ValueError("annotated_window_size deve ser maior que zero")
    if context_message_count < 0:
        raise ValueError("context_message_count nao pode ser negativo")
    rows = load_discord_export(
        input_path,
        guild_id=guild_id,
        guild_name=guild_name,
        channel_id=channel_id,
        channel_name=channel_name,
        preserve_native_fields=True,
    )
    messages, dropped_rows, duplicate_message_ids = _normalize_messages(rows)
    valid_edges, quality = _valid_direct_reply_edges(messages)
    annotation_windows = _build_annotation_windows(
        messages,
        valid_edges,
        annotated_window_size=annotated_window_size,
        context_message_count=context_message_count,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    filtered_messages_path = output_dir / "native_reply_messages.parquet"
    direct_reply_edges_path = output_dir / "native_reply_edges.parquet"
    annotation_windows_path = output_dir / "native_reply_annotation_windows.csv"
    summary_path = output_dir / "native_reply_summary.json"

    messages.to_parquet(filtered_messages_path, index=False)
    valid_edges.to_parquet(direct_reply_edges_path, index=False)
    annotation_windows.to_csv(
        annotation_windows_path,
        index=False,
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "input_path": str(input_path),
                "scope": {
                    "guild_id": guild_id,
                    "guild_name": guild_name,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                },
                "annotation_unit": "continuous_channel_window",
                "annotated_window_size": annotated_window_size,
                "context_message_count": context_message_count,
                "annotation_contract": {
                    "reply_sources": "Only messages with window_role=annotated require a reply annotation.",
                    "eligible_antecedents": "Any chronologically prior visible message, including window_role=context, may be selected as a parent.",
                    "outside_context": "Use parent_location=outside_context when the parent plausibly predates the visible context; do not infer a new conversation from a missing visible parent.",
                    "parent_location_values": [
                        "context",
                        "annotated",
                        "no_reply",
                        "outside_context",
                        "ambiguous",
                    ],
                    "native_reply_semantics": "A native_reply_to_message_id is positive observed evidence. A null value is unknown, never a negative semantic reply label.",
                    "human_annotation_unit": "directed_reply_edges",
                    "human_conversation_ids": "Derived from connected components after human reply edges are finalized; annotators do not assign conversation_id.",
                    "human_reply_edge_fields": [
                        "source_message_id",
                        "target_message_id",
                        "target_location",
                    ],
                    "human_source_annotation_status_values": [
                        "pending",
                        "complete",
                        "no_reply",
                        "outside_context",
                        "ambiguous",
                        "new_conversation",
                    ],
                },
                "filtered_message_count": int(len(messages)),
                "dropped_rows_missing_message_id_or_timestamp": dropped_rows,
                "duplicate_message_ids_discarded": duplicate_message_ids,
                "annotation_window_count": int(len(annotation_windows)),
                "annotated_message_count": int(
                    annotation_windows["annotated_message_count"].sum()
                ),
                "context_messages_included": int(
                    annotation_windows["context_message_count"].sum()
                ),
                **quality,
            },
            ensure_ascii=True,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    return GoldStandardArtifacts(
        filtered_messages_path=filtered_messages_path,
        direct_reply_edges_path=direct_reply_edges_path,
        annotation_windows_path=annotation_windows_path,
        summary_path=summary_path,
    )


def _normalize_messages(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, int, int]:
    records: list[dict[str, Any]] = []
    dropped_rows = 0
    for row in rows:
        message_id = _optional_text(row.get("message_id"))
        timestamp = pd.to_datetime(row.get("timestamp"), utc=True, errors="coerce")
        if message_id is None or pd.isna(timestamp):
            dropped_rows += 1
            continue
        channel_id = _optional_text(row.get("channel_id"))
        channel_name = _optional_text(row.get("channel_name"))
        reply_target_message_id = _reply_target_id(row)
        records.append(
            {
                "message_id": message_id,
                "guild_id": _optional_text(row.get("guild_id")),
            "server_id": _optional_text(row.get("guild_id")),
                "guild_name": _optional_text(row.get("guild_name")),
                "channel_id": channel_id,
                "channel_name": channel_name,
                "channel_key": f"{channel_id or ''}\0{channel_name or ''}",
                "native_thread_id": _optional_text(row.get("native_thread_id")),
                "author_id": _optional_text(row.get("author_id")),
            "author_username": _optional_text(row.get("author_username")),
            "author_discriminator": _optional_text(row.get("author_discriminator")),
                "timestamp": timestamp,
            "edited_timestamp": _optional_text(row.get("edited_timestamp")),
                "content": str(row.get("content") or ""),
            "reply_target_message_id": reply_target_message_id,
            "native_reply_to_message_id": reply_target_message_id,
                "mentions": row.get("mentions") or [],
            "reactions": row.get("reactions") or [],
                "attachments": row.get("attachments") or [],
                "embeds": row.get("embeds") or [],
            "mention_roles": row.get("mention_roles") or [],
            "sticker_items": row.get("sticker_items") or [],
                "is_bot": bool(row.get("is_bot")),
                "is_webhook": bool(row.get("is_webhook")),
                "webhook_id": _optional_text(row.get("webhook_id")),
            "pinned": bool(row.get("pinned")),
            "mention_everyone": bool(row.get("mention_everyone")),
            "tts": bool(row.get("tts")),
            "flags": row.get("flags"),
                "message_type": _optional_text(row.get("message_type")),
            "referenced_guild_id": _optional_text(row.get("referenced_guild_id")),
                "native_available_fields_json": row.get(
                    "native_available_fields_json",
                    "[]",
                ),
            "native_fields_json": row.get("native_fields_json", "{}"),
            }
        )
    messages = pd.DataFrame.from_records(records)
    if messages.empty:
        return messages, dropped_rows, 0
    messages.sort_values(["channel_key", "timestamp", "message_id"], inplace=True, kind="stable")
    duplicate_message_ids = int(messages.duplicated("message_id", keep="first").sum())
    messages = messages.drop_duplicates("message_id", keep="first").reset_index(drop=True)
    return messages, dropped_rows, duplicate_message_ids


def _valid_direct_reply_edges(messages: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    columns = (
        "source_message_id",
        "target_message_id",
        "channel_id",
        "channel_name",
        "source_timestamp",
        "target_timestamp",
    )
    if messages.empty:
        return pd.DataFrame(columns=columns), {
            "direct_reply_references_raw": 0,
            "direct_reply_references_valid_same_channel_past": 0,
            "direct_reply_target_missing_from_scope": 0,
            "direct_reply_cross_channel_excluded": 0,
            "direct_reply_non_past_excluded": 0,
        }

    by_id = messages.set_index("message_id", drop=False)
    edge_rows: list[dict[str, Any]] = []
    raw_count = 0
    missing_target = 0
    cross_channel = 0
    non_past_target = 0
    for source in messages.itertuples(index=False):
        target_id = _optional_text(source.reply_target_message_id)
        if target_id is None:
            continue
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
        edge_rows.append(
            {
                "source_message_id": source.message_id,
                "target_message_id": target_id,
                "channel_id": source.channel_id,
                "channel_name": source.channel_name,
                "source_timestamp": source.timestamp,
                "target_timestamp": target["timestamp"],
            }
        )
    edges = pd.DataFrame.from_records(edge_rows, columns=columns)
    return edges, {
        "direct_reply_references_raw": raw_count,
        "direct_reply_references_valid_same_channel_past": int(len(edges)),
        "direct_reply_target_missing_from_scope": missing_target,
        "direct_reply_cross_channel_excluded": cross_channel,
        "direct_reply_non_past_excluded": non_past_target,
    }


def _build_annotation_windows(
    messages: pd.DataFrame,
    valid_edges: pd.DataFrame,
    *,
    annotated_window_size: int,
    context_message_count: int,
) -> pd.DataFrame:
    """Partition each channel into fixed, continuous annotated windows.

    Direct replies are evidence within a window, never a criterion for its
    boundaries. Annotated windows are non-overlapping; their preceding context
    may overlap with the annotation span of an earlier window.
    """
    if messages.empty:
        return pd.DataFrame(columns=ANNOTATION_WINDOW_COLUMNS)

    window_rows: list[dict[str, Any]] = []
    for channel_key, channel_messages in messages.groupby("channel_key", sort=False):
        ordered = channel_messages.sort_values(
            ["timestamp", "message_id"], kind="stable"
        ).reset_index(drop=True)
        for annotation_start in range(0, len(ordered), annotated_window_size):
            annotation_end = min(annotation_start + annotated_window_size, len(ordered))
            context_start = max(0, annotation_start - context_message_count)
            context = ordered.iloc[context_start:annotation_start]
            annotated = ordered.iloc[annotation_start:annotation_end]
            window = ordered.iloc[context_start:annotation_end]
            window_message_ids = set(window["message_id"])
            annotated_message_ids = set(annotated["message_id"])
            window_id = _window_id(channel_key, str(annotated["message_id"].iloc[0]))
            visible_edges = valid_edges[
                valid_edges["source_message_id"].isin(window_message_ids)
                & valid_edges["target_message_id"].isin(window_message_ids)
            ].sort_values(["source_timestamp", "source_message_id"], kind="stable")
            annotated_edges = valid_edges[
                valid_edges["source_message_id"].isin(annotated_message_ids)
            ]
            outside_target_count = int(
                len(annotated_edges)
                - annotated_edges["target_message_id"].isin(window_message_ids).sum()
            )
            role_by_message_id = {
                message_id: "annotated" if message_id in annotated_message_ids else "context"
                for message_id in window_message_ids
            }
            native_reply_by_message_id = ordered.set_index("message_id")[
                "native_reply_to_message_id"
            ].to_dict()
            messages_payload = [
                {
                    "sequence": position,
                    "window_role": role_by_message_id[row.message_id],
                    "requires_reply_annotation": row.message_id in annotated_message_ids,
                    "eligible_as_antecedent_for_later_target": position < len(window),
                    "message_id": row.message_id,
                    "server_id": _optional_text(row.server_id),
                    "channel_id": _optional_text(row.channel_id),
                    "channel_name": _optional_text(row.channel_name),
                    "native_reply_to_message_id": _optional_text(
                        row.native_reply_to_message_id
                    ),
                    "native_reply_evidence": _native_reply_evidence(
                        row.native_reply_to_message_id
                    ),
                    "author_id": _optional_text(row.author_id),
                    "author_username": _optional_text(row.author_username),
                    "author_discriminator": _optional_text(row.author_discriminator),
                    "timestamp": row.timestamp.isoformat(),
                    "edited_timestamp": _optional_text(row.edited_timestamp),
                    "content": row.content,
                    "mentions": row.mentions,
                    "reactions": row.reactions,
                    "attachments": row.attachments,
                    "embeds": row.embeds,
                    "mention_roles": row.mention_roles,
                    "sticker_items": row.sticker_items,
                    "is_bot": row.is_bot,
                    "is_webhook": row.is_webhook,
                    "webhook_id": _optional_text(row.webhook_id),
                    "pinned": row.pinned,
                    "mention_everyone": row.mention_everyone,
                    "tts": row.tts,
                    "flags": _optional_int(row.flags),
                    "message_type": _optional_text(row.message_type),
                    "native_thread_id": _optional_text(row.native_thread_id),
                    "referenced_guild_id": _optional_text(row.referenced_guild_id),
                    "native_available_fields": json.loads(
                        row.native_available_fields_json
                    ),
                    "native_fields_json": row.native_fields_json,
                }
                for position, row in enumerate(window.itertuples(index=False), start=1)
            ]
            edges_payload = [
                {
                    "source_message_id": row.source_message_id,
                    "target_message_id": row.target_message_id,
                    "source_role": role_by_message_id[row.source_message_id],
                    "target_role": role_by_message_id[row.target_message_id],
                }
                for row in visible_edges.itertuples(index=False)
            ]
            source_annotation_statuses = [
                {
                    "source_message_id": message_id,
                    "native_reply_to_message_id": _optional_text(
                        native_reply_by_message_id[message_id]
                    ),
                    "native_reply_evidence": _native_reply_evidence(
                        native_reply_by_message_id[message_id]
                    ),
                    "source_annotation_status": "pending",
                }
                for message_id in annotated["message_id"]
            ]
            window_rows.append(
                {
                    "annotation_id": window_id,
                    "window_id": window_id,
                    "guild_id": annotated["guild_id"].iloc[0],
                    "guild_name": annotated["guild_name"].iloc[0],
                    "channel_id": annotated["channel_id"].iloc[0],
                    "channel_name": annotated["channel_name"].iloc[0],
                    "context_start_message_id": _first_or_none(context, "message_id"),
                    "context_end_message_id": _last_or_none(context, "message_id"),
                    "first_annotated_message_id": annotated["message_id"].iloc[0],
                    "last_annotated_message_id": annotated["message_id"].iloc[-1],
                    "context_start_timestamp": _first_or_none(context, "timestamp"),
                    "context_end_timestamp": _last_or_none(context, "timestamp"),
                    "annotation_start_timestamp": annotated["timestamp"].iloc[0],
                    "annotation_end_timestamp": annotated["timestamp"].iloc[-1],
                    "context_message_count": int(len(context)),
                    "annotated_message_count": int(len(annotated)),
                    "total_message_count": int(len(window)),
                    "participant_count": int(window["author_id"].nunique()),
                    "messages_json": json.dumps(messages_payload, ensure_ascii=True, default=str),
                    "native_reply_edges_json": json.dumps(edges_payload, ensure_ascii=True),
                    "native_reply_edges_visible_count": int(len(visible_edges)),
                    "native_reply_targets_outside_window_count": outside_target_count,
                    "native_reply_evidence_review": "pending",
                    "human_reply_edges_json": "[]",
                    "human_reply_source_statuses_json": json.dumps(
                        source_annotation_statuses,
                        ensure_ascii=True,
                    ),
                    "ambiguity": "pending",
                    "annotator_id": "",
                    "reviewed_at": "",
                    "notes": "",
                }
            )
    return pd.DataFrame.from_records(window_rows, columns=ANNOTATION_WINDOW_COLUMNS)


def _first_or_none(frame: pd.DataFrame, column: str) -> Any | None:
    return None if frame.empty else frame[column].iloc[0]


def _last_or_none(frame: pd.DataFrame, column: str) -> Any | None:
    return None if frame.empty else frame[column].iloc[-1]


def _reply_target_id(row: dict[str, Any]) -> str | None:
    direct = _optional_text(row.get("reply_to_message_id"))
    if direct is not None:
        return direct
    for field in ("message_reference", "referenced_message"):
        reference = row.get(field)
        if isinstance(reference, dict):
            for key in ("message_id", "messageId", "id"):
                target_id = _optional_text(reference.get(key))
                if target_id is not None:
                    return target_id
    return None


def _optional_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _native_reply_evidence(value: Any) -> str:
    return "positive_observed" if _optional_text(value) is not None else "unknown"


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _window_id(channel_key: str, first_annotated_message_id: str) -> str:
    identifier = f"{channel_key}\0{first_annotated_message_id}".encode("utf-8")
    return f"WINDOW_{hashlib.sha1(identifier).hexdigest()[:12]}"