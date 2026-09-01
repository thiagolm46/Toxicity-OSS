from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


HUMAN_REPLY_EDGE_COLUMNS: tuple[str, ...] = (
    "annotation_id",
    "window_id",
    "guild_id",
    "channel_id",
    "channel_name",
    "source_message_id",
    "target_message_id",
    "target_location",
)

HUMAN_COMPONENT_COLUMNS: tuple[str, ...] = (
    "conversation_id",
    "message_id",
    "guild_id",
    "channel_id",
    "channel_name",
    "component_message_count",
)

VALID_SOURCE_STATUSES = frozenset(
    {"pending", "complete", "no_reply", "outside_context", "ambiguous"}
)


@dataclass(frozen=True, slots=True)
class HumanAnnotationArtifacts:
    human_reply_edges_path: Path
    human_components_path: Path
    summary_path: Path


def materialize_human_reply_components(
    annotation_windows_path: Path,
    output_dir: Path,
) -> HumanAnnotationArtifacts:
    """Validate completed reply edges and derive conversation IDs by components."""
    windows = pd.read_csv(annotation_windows_path, keep_default_na=False)
    _require_columns(
        windows,
        {
            "annotation_id",
            "window_id",
            "guild_id",
            "channel_id",
            "channel_name",
            "messages_json",
            "human_reply_edges_json",
            "human_reply_source_statuses_json",
        },
    )
    edge_rows: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()
    for window in windows.itertuples(index=False):
        messages = _json_list(window.messages_json, "messages_json", window.annotation_id)
        statuses = _json_list(
            window.human_reply_source_statuses_json,
            "human_reply_source_statuses_json",
            window.annotation_id,
        )
        submitted_edges = _json_list(
            window.human_reply_edges_json,
            "human_reply_edges_json",
            window.annotation_id,
        )
        message_by_id = _message_index(messages, window.annotation_id)
        status_by_source = _status_index(statuses, message_by_id, window.annotation_id)
        for edge in submitted_edges:
            source_id, target_id, target_location = _validate_edge(
                edge,
                message_by_id=message_by_id,
                status_by_source=status_by_source,
                annotation_id=window.annotation_id,
            )
            if (source_id, target_id) in seen_edges:
                continue
            seen_edges.add((source_id, target_id))
            edge_rows.append(
                {
                    "annotation_id": str(window.annotation_id),
                    "window_id": str(window.window_id),
                    "guild_id": str(window.guild_id),
                    "channel_id": str(window.channel_id),
                    "channel_name": str(window.channel_name),
                    "source_message_id": source_id,
                    "target_message_id": target_id,
                    "target_location": target_location,
                }
            )

    edges = pd.DataFrame.from_records(edge_rows, columns=HUMAN_REPLY_EDGE_COLUMNS)
    components = _build_components(edges)
    output_dir.mkdir(parents=True, exist_ok=True)
    human_reply_edges_path = output_dir / "human_reply_edges.parquet"
    human_components_path = output_dir / "human_reply_components.parquet"
    summary_path = output_dir / "human_annotation_summary.json"
    edges.to_parquet(human_reply_edges_path, index=False)
    components.to_parquet(human_components_path, index=False)
    summary_path.write_text(
        json.dumps(
            {
                "annotation_windows_path": str(annotation_windows_path),
                "annotation_unit": "directed_reply_edges",
                "conversation_id_rule": "undirected_connected_components_of_human_reply_edges",
                "human_reply_edge_count": int(len(edges)),
                "human_conversation_count": int(components["conversation_id"].nunique()),
                "human_component_message_count": int(len(components)),
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return HumanAnnotationArtifacts(
        human_reply_edges_path=human_reply_edges_path,
        human_components_path=human_components_path,
        summary_path=summary_path,
    )


def _require_columns(frame: pd.DataFrame, required: set[str]) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(
            "Planilha de anotacao sem colunas obrigatorias: "
            + ", ".join(sorted(missing))
        )


def _json_list(value: Any, column: str, annotation_id: str) -> list[Any]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON invalido em {column} da janela {annotation_id}") from error
    if not isinstance(parsed, list):
        raise ValueError(f"{column} deve conter uma lista na janela {annotation_id}")
    return parsed


def _message_index(messages: list[Any], annotation_id: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for message in messages:
        if not isinstance(message, dict) or not message.get("message_id"):
            raise ValueError(f"Mensagem invalida na janela {annotation_id}")
        message_id = str(message["message_id"])
        if message_id in indexed:
            raise ValueError(f"message_id duplicado na janela {annotation_id}: {message_id}")
        indexed[message_id] = message
    return indexed


def _status_index(
    statuses: list[Any],
    message_by_id: dict[str, dict[str, Any]],
    annotation_id: str,
) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for status in statuses:
        if not isinstance(status, dict):
            raise ValueError(f"Status humano invalido na janela {annotation_id}")
        source_id = _required_value(status, "source_message_id", annotation_id)
        source_status = _required_value(
            status,
            "source_annotation_status",
            annotation_id,
        )
        source = message_by_id.get(source_id)
        if source is None or source.get("window_role") != "annotated":
            raise ValueError(f"Fonte humana invalida em {annotation_id}: {source_id}")
        if source_status not in VALID_SOURCE_STATUSES:
            raise ValueError(f"Status humano invalido em {annotation_id}: {source_status}")
        if source_id in indexed:
            raise ValueError(f"Status humano duplicado em {annotation_id}: {source_id}")
        indexed[source_id] = source_status
    return indexed


def _validate_edge(
    edge: Any,
    *,
    message_by_id: dict[str, dict[str, Any]],
    status_by_source: dict[str, str],
    annotation_id: str,
) -> tuple[str, str, str]:
    if not isinstance(edge, dict):
        raise ValueError(f"Aresta humana invalida em {annotation_id}")
    source_id = _required_value(edge, "source_message_id", annotation_id)
    target_id = _required_value(edge, "target_message_id", annotation_id)
    target_location = _required_value(edge, "target_location", annotation_id)
    source = message_by_id.get(source_id)
    target = message_by_id.get(target_id)
    if source is None or source.get("window_role") != "annotated":
        raise ValueError(f"Aresta humana tem fonte fora do trecho anotado: {source_id}")
    if target is None:
        raise ValueError(f"Aresta humana tem antecedente fora da janela: {target_id}")
    if status_by_source.get(source_id) != "complete":
        raise ValueError(f"Aresta humana exige fonte complete: {source_id}")
    if target_location not in {"context", "annotated"}:
        raise ValueError(f"Localizacao de antecedente invalida: {target_location}")
    if target.get("window_role") != target_location:
        raise ValueError(
            f"Localizacao declarada nao corresponde ao antecedente: {target_id}"
        )
    if int(target["sequence"]) >= int(source["sequence"]):
        raise ValueError(f"Antecedente nao e estritamente anterior: {source_id} -> {target_id}")
    return source_id, target_id, target_location


def _required_value(record: dict[str, Any], field: str, annotation_id: str) -> str:
    value = record.get(field)
    if value is None or not str(value).strip():
        raise ValueError(f"Registro humano sem {field} na janela {annotation_id}")
    return str(value)


def _build_components(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=HUMAN_COMPONENT_COLUMNS)
    graph = _UnionFind()
    metadata_by_message: dict[str, tuple[str, str, str]] = {}
    for edge in edges.itertuples(index=False):
        metadata = (str(edge.guild_id), str(edge.channel_id), str(edge.channel_name))
        for message_id in (str(edge.source_message_id), str(edge.target_message_id)):
            previous = metadata_by_message.setdefault(message_id, metadata)
            if previous != metadata:
                raise ValueError(f"Mensagem humana apareceu em canais distintos: {message_id}")
        graph.union(str(edge.source_message_id), str(edge.target_message_id))
    members_by_root: dict[str, list[str]] = {}
    for message_id in metadata_by_message:
        members_by_root.setdefault(graph.find(message_id), []).append(message_id)
    rows: list[dict[str, Any]] = []
    for members in members_by_root.values():
        ordered_members = sorted(members)
        guild_id, channel_id, channel_name = metadata_by_message[ordered_members[0]]
        conversation_id = _conversation_id(channel_id, ordered_members)
        for message_id in ordered_members:
            rows.append(
                {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "component_message_count": len(ordered_members),
                }
            )
    return pd.DataFrame.from_records(rows, columns=HUMAN_COMPONENT_COLUMNS)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _conversation_id(channel_id: str, message_ids: list[str]) -> str:
    identifier = (channel_id + "\0" + "\0".join(message_ids)).encode("utf-8")
    return f"HUMAN_{hashlib.sha1(identifier).hexdigest()[:12]}"