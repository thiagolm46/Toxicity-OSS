from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "message_id": ("message_id", "id", "ID", "Message ID", "MessageId"),
    "guild_id": ("guild_id", "guildId", "Guild ID", "server_id"),
    "channel_id": ("channel_id", "channelId", "Channel ID"),
    "channel_name": ("channel_name", "channelName", "Channel Name", "channel"),
    "native_thread_id": ("native_thread_id", "thread_id", "threadId", "Thread ID"),
    "author_id": ("author_id", "authorId", "Author ID", "author.id", "user_id"),
    "timestamp": ("timestamp", "Date", "date", "created_at", "Timestamp"),
    "edited_timestamp": ("edited_timestamp", "Edited Timestamp", "edited_at"),
    "content": ("content", "Content", "message", "Message"),
    "mentions": ("mentions", "Mentions"),
    "attachments": ("attachments", "Attachments"),
    "embeds": ("embeds", "Embeds"),
    "reactions": ("reactions", "Reactions"),
    "message_reference": ("message_reference", "messageReference", "reference"),
    "referenced_message": ("referenced_message", "referencedMessage"),
    "reply_to_message_id": ("reply_to_message_id", "replyToMessageId", "Reply To"),
    "is_bot": ("is_bot", "isBot", "Is Bot", "author.bot"),
    "is_webhook": ("is_webhook", "isWebhook", "webhook_id"),
    "message_type": ("message_type", "type", "Type"),
}


def load_discord_export(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError(f"Formato nao suportado: {path.suffix}. Use JSON ou CSV.")


def _load_json(path: Path) -> list[dict[str, Any]]:
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
    return [normalize_row(row) for row in rows]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        return [normalize_row(dict(row)) for row in reader]


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
        for key in ("guild_id", "guildId", "channel_id", "channelId", "channel_name", "channelName"):
            if key not in row and key in parent:
                row[key] = parent[key]
        if "guild" in parent and isinstance(parent["guild"], dict):
            row.setdefault("guild_id", parent["guild"].get("id"))
        if "channel" in parent and isinstance(parent["channel"], dict):
            row.setdefault("channel_id", parent["channel"].get("id"))
            row.setdefault("channel_name", parent["channel"].get("name"))
        rows.append(row)
    return rows


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        normalized[canonical] = _first_value(row, aliases)

    author = row.get("author")
    if isinstance(author, dict):
        normalized["author_id"] = normalized["author_id"] or author.get("id")
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
    normalized["channel_id"] = as_str(normalized["channel_id"])
    normalized["channel_name"] = as_str(normalized["channel_name"])
    normalized["native_thread_id"] = as_str(normalized["native_thread_id"])
    normalized["author_id"] = as_str(normalized["author_id"])
    normalized["reply_to_message_id"] = as_str(normalized["reply_to_message_id"])
    normalized["timestamp"] = parse_timestamp(normalized["timestamp"])
    normalized["edited_timestamp"] = as_str(normalized["edited_timestamp"])
    normalized["content"] = "" if normalized["content"] is None else str(normalized["content"])
    normalized["mentions"] = parse_jsonish(normalized["mentions"], default=[])
    normalized["attachments"] = parse_jsonish(normalized["attachments"], default=[])
    normalized["embeds"] = parse_jsonish(normalized["embeds"], default=[])
    normalized["reactions"] = parse_jsonish(normalized["reactions"], default=[])
    normalized["message_reference"] = parse_jsonish(normalized["message_reference"], default=None)
    normalized["referenced_message"] = parse_jsonish(normalized["referenced_message"], default=None)
    normalized["is_bot"] = as_bool(normalized["is_bot"])
    normalized["is_webhook"] = as_bool(normalized["is_webhook"])
    return normalized


def _first_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in ("", None):
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
            if found and value not in ("", None):
                return value
    return None


def parse_jsonish(value: Any, default: Any) -> Any:
    if value in (None, ""):
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
    elif value in (None, ""):
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
    if value in (None, ""):
        return None
    return str(value)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "sim"}

