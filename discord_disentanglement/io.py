from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "message_id": ("message_id", "id", "ID", "Message ID", "MessageId"),
    "guild_id": ("guild_id", "guildId", "Guild ID", "server_id"),
    "guild_name": ("guild_name", "guildName", "Guild Name", "server_name"),
    "channel_id": ("channel_id", "channelId", "Channel ID"),
    "channel_name": ("channel_name", "channelName", "Channel Name", "channel"),
    "native_thread_id": ("native_thread_id", "thread_id", "threadId", "Thread ID"),
    "author_id": ("author_id", "authorId", "Author ID", "author.id", "user_id"),
    "author_username": ("author_username", "authorUsername", "author.username"),
    "author_discriminator": (
        "author_discriminator",
        "authorDiscriminator",
        "author.discriminator",
    ),
    "timestamp": ("timestamp", "Date", "date", "created_at", "Timestamp"),
    "edited_timestamp": ("edited_timestamp", "Edited Timestamp", "edited_at"),
    "content": ("content", "Content", "message", "Message"),
    "mentions": ("mentions", "Mentions", "mentions_json"),
    "attachments": ("attachments", "Attachments", "attachments_json"),
    "embeds": ("embeds", "Embeds", "embeds_json"),
    "reactions": ("reactions", "Reactions", "reactions_json"),
    "mention_roles": ("mention_roles", "mentionRoles", "mention_roles_json"),
    "sticker_items": ("sticker_items", "stickerItems", "sticker_items_json"),
    "message_reference": ("message_reference", "messageReference", "reference"),
    "referenced_message": ("referenced_message", "referencedMessage"),
    "reply_to_message_id": (
        "reply_to_message_id",
        "replyToMessageId",
        "Reply To",
        "referenced_message_id",
    ),
    "is_bot": ("is_bot", "isBot", "Is Bot", "author.bot"),
    "is_webhook": ("is_webhook", "isWebhook"),
    "webhook_id": ("webhook_id", "webhookId"),
    "message_type": ("message_type", "type", "Type"),
    "pinned": ("pinned", "Pinned"),
    "mention_everyone": ("mention_everyone", "mentionEveryone"),
    "tts": ("tts", "TTS"),
    "flags": ("flags", "Flags"),
    "referenced_guild_id": ("referenced_guild_id", "referencedGuildId"),
}


def load_discord_export(
    path: Path,
    guild_name: str | None = None,
    guild_id: str | None = None,
    channel_name: str | None = None,
    channel_id: str | None = None,
    preserve_native_fields: bool = False,
) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        rows = _load_json(path, preserve_native_fields=preserve_native_fields)
        return filter_rows(rows, guild_name, guild_id, channel_name, channel_id)
    if suffix == ".csv":
        rows = _load_csv(path, preserve_native_fields=preserve_native_fields)
        return filter_rows(rows, guild_name, guild_id, channel_name, channel_id)
    if suffix in {".parquet", ".pq"}:
        return _load_parquet(
            path,
            guild_name,
            guild_id,
            channel_name,
            channel_id,
            preserve_native_fields=preserve_native_fields,
        )
    raise ValueError(f"Formato nao suportado: {path.suffix}. Use JSON, CSV ou Parquet.")


def _load_json(path: Path, *, preserve_native_fields: bool) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        rows.extend(_flatten_message_rows(data))
    elif isinstance(data, dict):
        if isinstance(data.get("messages"), list):
            rows.extend(_flatten_message_rows(data["messages"], parent=data))
        elif isinstance(data.get("channels"), list):
            for channel in data["channels"]:
                if isinstance(channel, dict) and isinstance(channel.get("messages"), list):
                    rows.extend(_flatten_message_rows(channel["messages"], parent={**data, **channel}))
        else:
            rows.extend(_flatten_message_rows([data]))
    return [normalize_row(row, preserve_native_fields=preserve_native_fields) for row in rows]


def _load_csv(path: Path, *, preserve_native_fields: bool) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        return [
            normalize_row(dict(row), preserve_native_fields=preserve_native_fields)
            for row in reader
        ]


def _load_parquet(
    path: Path,
    guild_name: str | None,
    guild_id: str | None,
    channel_name: str | None,
    channel_id: str | None,
    *,
    preserve_native_fields: bool,
) -> list[dict[str, Any]]:
    schema_columns = pq.ParquetFile(path).schema.names
    available_columns = set(schema_columns)
    columns = (
        schema_columns
        if preserve_native_fields
        else [
            alias
            for aliases in FIELD_ALIASES.values()
            for alias in aliases
            if "." not in alias and alias in available_columns
        ]
    )
    filters: list[tuple[str, str, str]] = []
    for column, value in (
        ("guild_id", guild_id),
        ("guild_name", guild_name),
        ("channel_id", channel_id),
        ("channel_name", channel_name),
    ):
        if value and column in available_columns:
            filters.append((column, "==", value))
    dataframe = pd.read_parquet(
        path,
        columns=columns or None,
        filters=filters or None,
    )
    if guild_id and "guild_id" in dataframe.columns:
        dataframe = dataframe[dataframe["guild_id"].astype(str) == str(guild_id)]
    if guild_name and "guild_name" in dataframe.columns:
        dataframe = dataframe[
            dataframe["guild_name"].astype(str).str.casefold() == guild_name.casefold()
        ]
    if channel_id and "channel_id" in dataframe.columns:
        dataframe = dataframe[dataframe["channel_id"].astype(str) == str(channel_id)]
    if channel_name and "channel_name" in dataframe.columns:
        dataframe = dataframe[
            dataframe["channel_name"].astype(str).str.casefold() == channel_name.casefold()
        ]
    return [
        normalize_row(row, preserve_native_fields=preserve_native_fields)
        for row in dataframe.to_dict(orient="records")
    ]


def filter_rows(
    rows: list[dict[str, Any]],
    guild_name: str | None,
    guild_id: str | None,
    channel_name: str | None,
    channel_id: str | None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if _matches_value(row.get("guild_id"), guild_id)
        and _matches_text(row.get("guild_name"), guild_name)
        and _matches_value(row.get("channel_id"), channel_id)
        and _matches_text(row.get("channel_name"), channel_name)
    ]


def _flatten_message_rows(
    messages: Iterable[Any],
    parent: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    parent = parent or {}
    for item in messages:
        if not isinstance(item, dict):
            continue
        row = dict(item)
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
            if key not in row and key in parent:
                row[key] = parent[key]
        if "guild" in parent and isinstance(parent["guild"], dict):
            row.setdefault("guild_id", parent["guild"].get("id"))
            row.setdefault("guild_name", parent["guild"].get("name"))
        if "channel" in parent and isinstance(parent["channel"], dict):
            row.setdefault("channel_id", parent["channel"].get("id"))
            row.setdefault("channel_name", parent["channel"].get("name"))
        rows.append(row)
    return rows


def normalize_row(
    row: dict[str, Any],
    *,
    preserve_native_fields: bool = False,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        normalized[canonical] = _first_value(row, aliases)

    author = row.get("author")
    if isinstance(author, dict):
        normalized["author_id"] = normalized["author_id"] or author.get("id")
        normalized["author_username"] = normalized["author_username"] or author.get("username")
        normalized["author_discriminator"] = (
            normalized["author_discriminator"] or author.get("discriminator")
        )
        normalized["is_bot"] = normalized["is_bot"] if normalized["is_bot"] is not None else author.get("bot")

    channel = row.get("channel")
    if isinstance(channel, dict):
        normalized["channel_id"] = normalized["channel_id"] or channel.get("id")
        normalized["channel_name"] = normalized["channel_name"] or channel.get("name")

    thread = row.get("thread")
    if isinstance(thread, dict):
        normalized["native_thread_id"] = normalized["native_thread_id"] or thread.get("id")

    normalized["message_id"] = as_str(normalized["message_id"])
    normalized["guild_id"] = as_str(normalized["guild_id"])
    normalized["guild_name"] = as_str(normalized["guild_name"])
    normalized["channel_id"] = as_str(normalized["channel_id"])
    normalized["channel_name"] = as_str(normalized["channel_name"])
    normalized["native_thread_id"] = as_str(normalized["native_thread_id"])
    normalized["author_id"] = as_str(normalized["author_id"])
    normalized["author_username"] = as_str(normalized["author_username"])
    normalized["author_discriminator"] = as_str(normalized["author_discriminator"])
    normalized["reply_to_message_id"] = as_str(normalized["reply_to_message_id"])
    normalized["referenced_guild_id"] = as_str(normalized["referenced_guild_id"])
    normalized["webhook_id"] = as_str(normalized["webhook_id"])
    normalized["timestamp"] = parse_timestamp(normalized["timestamp"])
    normalized["edited_timestamp"] = as_str(normalized["edited_timestamp"])
    normalized["content"] = "" if normalized["content"] is None else str(normalized["content"])
    normalized["mentions"] = parse_jsonish(normalized["mentions"], default=[])
    normalized["attachments"] = parse_jsonish(normalized["attachments"], default=[])
    normalized["embeds"] = parse_jsonish(normalized["embeds"], default=[])
    normalized["reactions"] = parse_jsonish(normalized["reactions"], default=[])
    normalized["mention_roles"] = parse_jsonish(normalized["mention_roles"], default=[])
    normalized["sticker_items"] = parse_jsonish(normalized["sticker_items"], default=[])
    normalized["message_reference"] = parse_jsonish(normalized["message_reference"], default=None)
    normalized["referenced_message"] = parse_jsonish(normalized["referenced_message"], default=None)
    normalized["is_bot"] = as_bool(normalized["is_bot"])
    normalized["is_webhook"] = as_bool(normalized["is_webhook"])
    normalized["pinned"] = as_bool(normalized["pinned"])
    normalized["mention_everyone"] = as_bool(normalized["mention_everyone"])
    normalized["tts"] = as_bool(normalized["tts"])
    if preserve_native_fields:
        normalized["native_available_fields_json"] = json.dumps(
            sorted(str(key) for key in row),
            ensure_ascii=True,
        )
        normalized["native_fields_json"] = json.dumps(
            _json_compatible(row),
            ensure_ascii=True,
            sort_keys=True,
            default=str,
            allow_nan=False,
        )
    return normalized


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and not is_missing(row[alias]) and row[alias] != "":
            return row[alias]
        if "." in alias:
            value: Any = row
            found = True
            for part in alias.split("."):
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    found = False
                    break
            if found and not is_missing(value) and value != "":
                return value
    return None


def parse_jsonish(value: Any, default: Any) -> Any:
    if is_missing(value) or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        if stripped[0] in "[{":
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return default
    return default


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif is_missing(value) or value == "":
        parsed = datetime.now(timezone.utc)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_str(value: Any) -> str | None:
    if is_missing(value) or value == "":
        return None
    return str(value)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if is_missing(value) or value == "":
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "sim"}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return None if is_missing(value) else value


def _matches_value(actual: Any, expected: str | None) -> bool:
    if expected is None:
        return True
    return str(actual or "") == str(expected)


def _matches_text(actual: Any, expected: str | None) -> bool:
    if expected is None:
        return True
    return str(actual or "").casefold() == expected.casefold()

