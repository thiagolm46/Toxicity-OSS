from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from discord_disentanglement.io import load_discord_export


CONVERSATION_COLUMNS: tuple[str, ...] = (
    "conversation_id",
    "root_message_id",
    "guild_id",
    "guild_name",
    "channel_id",
    "channel_name",
    "start_timestamp",
    "end_timestamp",
    "duration_seconds",
    "message_count",
    "direct_reply_count",
    "participant_count",
    "messages_json",
    "reply_edges_json",
)

ANNOTATION_COLUMNS: tuple[str, ...] = (
    "annotation_id",
    "conversation_id",
    "root_message_id",
    "guild_id",
    "guild_name",
    "channel_id",
    "channel_name",
    "start_timestamp",
    "end_timestamp",
    "message_count",
    "direct_reply_count",
    "participant_count",
    "messages_json",
    "reply_edges_json",
    "reply_edges_valid",
    "conversation_complete",
    "ambiguity",
    "annotator_id",
    "reviewed_at",
    "notes",
)


@dataclass(frozen=True, slots=True)
class GoldStandardArtifacts:
    filtered_messages_path: Path
    direct_reply_edges_path: Path
    conversations_path: Path
    annotation_queue_path: Path
    summary_path: Path


def export_native_reply_gold_standard(
    input_path: Path,
    output_dir: Path,
    *,
    guild_id: str | None = None,
    guild_name: str | None = None,
    channel_id: str | None = None,
    channel_name: str | None = None,
) -> GoldStandardArtifacts:
    """Export native Discord reply components as human-annotation conversations."""
    rows = load_discord_export(
        input_path,
        guild_id=guild_id,
        guild_name=guild_name,
        channel_id=channel_id,
        channel_name=channel_name,
    )
    messages, dropped_rows, duplicate_message_ids = _normalize_messages(rows)
    valid_edges, quality = _valid_direct_reply_edges(messages)
    conversations, edges = _build_conversations(messages, valid_edges)

    output_dir.mkdir(parents=True, exist_ok=True)
    filtered_messages_path = output_dir / "native_reply_messages.parquet"
    direct_reply_edges_path = output_dir / "native_reply_edges.parquet"
    conversations_path = output_dir / "native_reply_conversations.parquet"
    annotation_queue_path = output_dir / "native_reply_annotation_queue.csv"
    summary_path = output_dir / "native_reply_summary.json"

    messages.to_parquet(filtered_messages_path, index=False)
    edges.to_parquet(direct_reply_edges_path, index=False)
    conversations.to_parquet(conversations_path, index=False)
    _build_annotation_queue(conversations).to_csv(
        annotation_queue_path,
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
                "filtered_message_count": int(len(messages)),
                "dropped_rows_missing_message_id_or_timestamp": dropped_rows,
                "duplicate_message_ids_discarded": duplicate_message_ids,
                "conversation_count": int(len(conversations)),
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
        conversations_path=conversations_path,
        annotation_queue_path=annotation_queue_path,
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
        records.append(
            {
                "message_id": message_id,
                "guild_id": _optional_text(row.get("guild_id")),
                "guild_name": _optional_text(row.get("guild_name")),
                "channel_id": channel_id,
                "channel_name": channel_name,
                "channel_key": f"{channel_id or ''}\0{channel_name or ''}",
                "native_thread_id": _optional_text(row.get("native_thread_id")),
                "author_id": _optional_text(row.get("author_id")),
                "timestamp": timestamp,
                "content": str(row.get("content") or ""),
                "reply_target_message_id": _reply_target_id(row),
                "mentions": row.get("mentions") or [],
                "attachments": row.get("attachments") or [],
                "embeds": row.get("embeds") or [],
                "is_bot": bool(row.get("is_bot")),
                "is_webhook": bool(row.get("is_webhook")),
                "message_type": _optional_text(row.get("message_type")),
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
        target_id = source.reply_target_message_id
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


def _build_conversations(
    messages: pd.DataFrame,
    valid_edges: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if valid_edges.empty:
        return pd.DataFrame(columns=CONVERSATION_COLUMNS), valid_edges.copy()

    parent_by_message = dict(
        zip(
            valid_edges["source_message_id"].astype(str),
            valid_edges["target_message_id"].astype(str),
            strict=False,
        )
    )
    root_by_message: dict[str, str] = {}

    def root_for(message_id: str) -> str:
        if message_id in root_by_message:
            return root_by_message[message_id]
        path: list[str] = []
        current = message_id
        while current in parent_by_message:
            path.append(current)
            current = parent_by_message[current]
        for visited in path:
            root_by_message[visited] = current
        root_by_message.setdefault(current, current)
        return current

    component_message_ids = set(valid_edges["source_message_id"]).union(
        valid_edges["target_message_id"]
    )
    component_messages = messages[messages["message_id"].isin(component_message_ids)].copy()
    component_messages["root_message_id"] = component_messages["message_id"].map(root_for)
    component_messages["conversation_id"] = component_messages.apply(
        lambda row: _conversation_id(row["channel_key"], row["root_message_id"]),
        axis=1,
    )
    conversation_by_message = component_messages.set_index("message_id")["conversation_id"].to_dict()
    edges = valid_edges.copy()
    edges.insert(
        0,
        "conversation_id",
        edges["source_message_id"].map(conversation_by_message),
    )

    conversation_rows: list[dict[str, Any]] = []
    for conversation_id, group in component_messages.groupby("conversation_id", sort=False):
        ordered = group.sort_values(["timestamp", "message_id"], kind="stable")
        root_message_id = str(ordered["root_message_id"].iloc[0])
        start_timestamp = ordered["timestamp"].iloc[0]
        end_timestamp = ordered["timestamp"].iloc[-1]
        messages_payload = [
            {
                "sequence": position,
                "message_id": row.message_id,
                "reply_to_message_id": parent_by_message.get(row.message_id),
                "author_id": row.author_id,
                "timestamp": row.timestamp.isoformat(),
                "content": row.content,
                "mentions": row.mentions,
                "attachments": row.attachments,
                "embeds": row.embeds,
                "is_bot": row.is_bot,
                "is_webhook": row.is_webhook,
                "message_type": row.message_type,
            }
            for position, row in enumerate(ordered.itertuples(index=False), start=1)
        ]
        conversation_edges = edges[edges["conversation_id"] == conversation_id]
        reply_edges_payload = [
            {
                "source_message_id": row.source_message_id,
                "target_message_id": row.target_message_id,
            }
            for row in conversation_edges.itertuples(index=False)
        ]
        conversation_rows.append(
            {
                "conversation_id": conversation_id,
                "root_message_id": root_message_id,
                "guild_id": ordered["guild_id"].iloc[0],
                "guild_name": ordered["guild_name"].iloc[0],
                "channel_id": ordered["channel_id"].iloc[0],
                "channel_name": ordered["channel_name"].iloc[0],
                "start_timestamp": start_timestamp,
                "end_timestamp": end_timestamp,
                "duration_seconds": float((end_timestamp - start_timestamp).total_seconds()),
                "message_count": int(len(ordered)),
                "direct_reply_count": int(len(conversation_edges)),
                "participant_count": int(ordered["author_id"].nunique()),
                "messages_json": json.dumps(messages_payload, ensure_ascii=True, default=str),
                "reply_edges_json": json.dumps(reply_edges_payload, ensure_ascii=True),
            }
        )
    conversations = pd.DataFrame.from_records(conversation_rows, columns=CONVERSATION_COLUMNS)
    return conversations, edges


def _build_annotation_queue(conversations: pd.DataFrame) -> pd.DataFrame:
    queue = conversations.copy()
    queue.insert(0, "annotation_id", queue["conversation_id"])
    queue["reply_edges_valid"] = "pending"
    queue["conversation_complete"] = "pending"
    queue["ambiguity"] = "pending"
    queue["annotator_id"] = ""
    queue["reviewed_at"] = ""
    queue["notes"] = ""
    return queue.reindex(columns=ANNOTATION_COLUMNS)


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


def _conversation_id(channel_key: str, root_message_id: str) -> str:
    identifier = f"{channel_key}\0{root_message_id}".encode("utf-8")
    return f"NATIVE_{hashlib.sha1(identifier).hexdigest()[:12]}"