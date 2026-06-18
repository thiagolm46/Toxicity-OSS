from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class MessageRecord:
    message_id: str
    guild_id: str | None
    guild_name: str | None
    channel_id: str | None
    channel_name: str | None
    native_thread_id: str | None
    author_id: str | None
    timestamp: datetime
    edited_timestamp: str | None
    content_raw: str
    content_normalized: str
    mentions: list[str] = field(default_factory=list)
    channel_mentions: list[str] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    embeds: list[dict[str, Any]] = field(default_factory=list)
    reactions: list[dict[str, Any]] = field(default_factory=list)
    message_reference: Any = None
    referenced_message: Any = None
    reply_to_message_id: str | None = None
    is_bot: bool = False
    is_webhook: bool = False
    message_type: str | int | None = None
    author_anon: str | None = None
    mention_anons: list[str] = field(default_factory=list)
    has_attachment: bool = False
    has_code_block: bool = False
    has_url: bool = False
    url_hosts: list[str] = field(default_factory=list)
    message_link_targets: list[str] = field(default_factory=list)
    code_or_error_marker: bool = False
    tokens: list[str] = field(default_factory=list)
    technical_tokens: list[str] = field(default_factory=list)

    @property
    def timestamp_iso(self) -> str:
        return self.timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class EdgeRecord:
    source_message_id: str
    target_message_id: str
    edge_type: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)
    method: str = "explicit"
    candidate_rank: int | None = None
    alternative_parents: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ThreadRecord:
    thread_id: str
    root_message_id: str
    message_ids: list[str]
    participants: list[str]
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    message_count: int
    participant_count: int
    avg_confidence: float
    min_confidence: float
    explicit_edge_count: int
    inferred_edge_count: int
    uncertain_edge_count: int
    keywords: list[str]
    conversation_shape: str
    status: str
    needs_review_reasons: list[str]
    title: str
    neutral_summary: str
