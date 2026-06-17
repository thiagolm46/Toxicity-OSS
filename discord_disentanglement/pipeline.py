from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from .io import load_discord_export
from .models import EdgeRecord, MessageRecord, ThreadRecord
from .reports import (
    generate_main_html_report,
    generate_summary_markdown,
    generate_thread_graph_reports,
)
from .text import (
    CODE_BLOCK_RE,
    DISAGREEMENT_RE,
    DISCORD_MESSAGE_URL_RE,
    ERROR_MARKER_RE,
    INLINE_CODE_RE,
    REASON_RE,
    SECOND_PERSON_RE,
    build_tfidf_vectors,
    cosine_similarity,
    evidence_labels,
    extract_url_hosts,
    lexical_overlap,
    normalize_content,
    question_score,
    response_marker_score,
    technical_tokens,
    tokenize,
)


@dataclass(slots=True)
class DisentanglementConfig:
    input_path: Path
    out_dir: Path
    guild_name: str | None = None
    guild_id: str | None = None
    channel_name: str | None = None
    channel_id: str | None = None
    threshold: float = 0.50
    uncertain_threshold: float = 0.60
    previous_message_window: int = 50
    time_window_hours: float = 24.0
    similarity_scan_limit: int = 250
    max_candidates_per_message: int = 150
    split_gap_hours: float = 6.0
    preserve_raw_content: bool = False
    export_neo4j: bool = True


def run_pipeline(config: DisentanglementConfig) -> dict[str, Path]:
    rows = load_discord_export(
        config.input_path,
        guild_name=config.guild_name,
        guild_id=config.guild_id,
        channel_name=config.channel_name,
        channel_id=config.channel_id,
    )
    messages = normalize_messages(
        rows,
        guild_name=config.guild_name,
        guild_id=config.guild_id,
        channel_name=config.channel_name,
        channel_id=config.channel_id,
        preserve_raw_content=config.preserve_raw_content,
    )
    if not messages:
        raise ValueError("Nenhuma mensagem encontrada para o escopo informado.")

    out_dir = config.out_dir
    reports_dir = out_dir / "reports"
    exports_dir = out_dir / "exports"
    graph_reports_dir = reports_dir / "thread_graphs"
    for directory in (out_dir, reports_dir, exports_dir, graph_reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    explicit_edges = extract_explicit_edges(messages)
    candidate_pairs = generate_candidate_pairs(
        messages=messages,
        explicit_edges=explicit_edges,
        threshold=config.threshold,
        uncertain_threshold=config.uncertain_threshold,
        previous_message_window=config.previous_message_window,
        time_window_hours=config.time_window_hours,
        similarity_scan_limit=config.similarity_scan_limit,
        max_candidates_per_message=config.max_candidates_per_message,
    )
    inferred_edges = select_inferred_edges(
        candidate_pairs=candidate_pairs,
        explicit_edges=explicit_edges,
        threshold=config.threshold,
        uncertain_threshold=config.uncertain_threshold,
    )
    graph_edges = explicit_edges + inferred_edges
    graph = build_graph(messages, graph_edges)
    threads = extract_threads(
        messages=messages,
        graph_edges=graph_edges,
        split_gap_hours=config.split_gap_hours,
    )
    thread_by_message = assign_thread_ids(messages, threads)
    thread_messages = build_thread_messages(messages, graph_edges, thread_by_message)
    review_rows = build_annotation_review(thread_messages)
    merge_suggestions = suggest_merges(threads)

    messages_df = messages_to_dataframe(messages, preserve_raw_content=config.preserve_raw_content)
    explicit_df = edges_to_dataframe(explicit_edges)
    candidate_df = pd.DataFrame(candidate_pairs)
    inferred_df = edges_to_dataframe(inferred_edges)
    graph_edges_df = edges_to_dataframe(graph_edges)
    threads_df = threads_to_dataframe(threads)
    thread_messages_df = pd.DataFrame(thread_messages)
    thread_summaries_df = thread_summaries_to_dataframe(threads)
    review_df = pd.DataFrame(review_rows)

    messages_df.to_csv(out_dir / "messages_normalized.csv", index=False)
    explicit_df.to_csv(out_dir / "edges_explicit.csv", index=False)
    candidate_df.to_csv(out_dir / "candidate_pairs.csv", index=False)
    inferred_df.to_csv(out_dir / "edges_inferred.csv", index=False)
    graph_edges_df.to_csv(out_dir / "graph_edges.csv", index=False)
    threads_df.to_csv(out_dir / "threads.csv", index=False)
    thread_messages_df.to_csv(out_dir / "thread_messages.csv", index=False)
    thread_summaries_df.to_csv(out_dir / "thread_summaries.csv", index=False)
    review_df.to_csv(out_dir / "annotation_review.csv", index=False)
    write_threads_json(threads, thread_messages, out_dir / "threads.json")
    write_graph_exports(graph, out_dir)
    generate_thread_graph_reports(
        threads=threads,
        messages=messages,
        graph_edges=graph_edges,
        output_dir=graph_reports_dir,
    )
    generate_main_html_report(
        threads=threads,
        messages=messages,
        graph_edges=graph_edges,
        thread_messages=thread_messages,
        candidate_pairs=candidate_pairs,
        output_path=reports_dir / "neo4j_threads.html",
    )
    generate_summary_markdown(
        threads=threads,
        messages=messages,
        graph_edges=graph_edges,
        merge_suggestions=merge_suggestions,
        output_path=reports_dir / "neo4j_threads_summary.md",
    )
    if config.export_neo4j:
        write_neo4j_exports(
            messages=messages,
            threads=threads,
            graph_edges=graph_edges,
            thread_by_message=thread_by_message,
            output_dir=exports_dir,
        )

    return {
        "messages": out_dir / "messages_normalized.csv",
        "explicit_edges": out_dir / "edges_explicit.csv",
        "candidate_pairs": out_dir / "candidate_pairs.csv",
        "inferred_edges": out_dir / "edges_inferred.csv",
        "graph_edges": out_dir / "graph_edges.csv",
        "threads": out_dir / "threads.csv",
        "threads_json": out_dir / "threads.json",
        "thread_messages": out_dir / "thread_messages.csv",
        "thread_summaries": out_dir / "thread_summaries.csv",
        "html_report": reports_dir / "neo4j_threads.html",
        "summary": reports_dir / "neo4j_threads_summary.md",
        "neo4j_users": exports_dir / "neo4j_users.csv",
        "neo4j_threads": exports_dir / "neo4j_threads.csv",
        "neo4j_messages": exports_dir / "neo4j_messages.csv",
        "neo4j_authored": exports_dir / "neo4j_authored_relationships.csv",
        "neo4j_belongs_to": exports_dir / "neo4j_belongs_to_relationships.csv",
        "neo4j_replies_to": exports_dir / "neo4j_replies_to_relationships.csv",
        "cypher": exports_dir / "neo4j_import.cypher",
    }


def normalize_messages(
    rows: list[dict[str, Any]],
    guild_name: str | None,
    guild_id: str | None,
    channel_name: str | None,
    channel_id: str | None,
    preserve_raw_content: bool,
) -> list[MessageRecord]:
    filtered = [
        row
        for row in rows
        if _matches_scope(
            row=row,
            guild_name=guild_name,
            guild_id=guild_id,
            channel_name=channel_name,
            channel_id=channel_id,
        )
    ]
    filtered.sort(key=lambda row: (row["timestamp"], row.get("message_id") or ""))

    author_alias_by_id: dict[str, str] = {}
    channel_alias_by_id: dict[str, str] = {}
    messages: list[MessageRecord] = []

    for index, row in enumerate(filtered):
        message_id = row.get("message_id") or f"m_{index + 1:06d}"
        author_id = row.get("author_id") or "unknown"
        author_anon = author_alias_by_id.setdefault(
            str(author_id), f"USER_{len(author_alias_by_id) + 1:03d}"
        )
        attachments = _dict_list(row.get("attachments"))
        content_raw = str(row.get("content") or "")
        normalized, inline_mentions, channel_mentions = normalize_content(
            content=content_raw,
            author_alias_by_id=author_alias_by_id,
            channel_alias_by_id=channel_alias_by_id,
            attachments=attachments,
        )
        structured_mentions = _mention_ids(row.get("mentions"))
        mention_ids = _dedupe([*inline_mentions, *structured_mentions])
        mention_anons = [
            author_alias_by_id.setdefault(user_id, f"USER_{len(author_alias_by_id) + 1:03d}")
            for user_id in mention_ids
        ]
        tokens = tokenize(normalized)
        tech_tokens = technical_tokens(tokens)
        has_code = bool(CODE_BLOCK_RE.search(content_raw) or INLINE_CODE_RE.search(content_raw))
        has_url = bool(extract_url_hosts(content_raw))
        record = MessageRecord(
            message_id=str(message_id),
            guild_id=row.get("guild_id"),
            guild_name=row.get("guild_name"),
            channel_id=row.get("channel_id"),
            channel_name=row.get("channel_name"),
            native_thread_id=row.get("native_thread_id"),
            author_id=str(author_id),
            timestamp=row["timestamp"],
            edited_timestamp=row.get("edited_timestamp"),
            content_raw=content_raw if preserve_raw_content else "",
            content_normalized=normalized,
            mentions=mention_ids,
            channel_mentions=channel_mentions,
            attachments=attachments,
            embeds=_dict_list(row.get("embeds")),
            reactions=_dict_list(row.get("reactions")),
            message_reference=row.get("message_reference"),
            referenced_message=row.get("referenced_message"),
            reply_to_message_id=row.get("reply_to_message_id"),
            is_bot=bool(row.get("is_bot")),
            is_webhook=bool(row.get("is_webhook")),
            message_type=row.get("message_type"),
            author_anon=author_anon,
            mention_anons=mention_anons,
            has_attachment=bool(attachments),
            has_code_block=has_code,
            has_url=has_url,
            url_hosts=extract_url_hosts(content_raw),
            message_link_targets=[
                match.group("message") for match in DISCORD_MESSAGE_URL_RE.finditer(content_raw)
            ],
            code_or_error_marker=has_code or bool(ERROR_MARKER_RE.search(content_raw)),
            tokens=tokens,
            technical_tokens=tech_tokens,
        )
        messages.append(record)
    return messages


def extract_explicit_edges(messages: list[MessageRecord]) -> list[EdgeRecord]:
    id_set = {message.message_id for message in messages}
    by_thread: dict[str, list[MessageRecord]] = defaultdict(list)
    edges: list[EdgeRecord] = []

    for message in messages:
        if message.native_thread_id:
            by_thread[str(message.native_thread_id)].append(message)
        targets = []
        for field_name, value in (
            ("reply_to_message_id", message.reply_to_message_id),
            ("message_reference", _reference_id(message.message_reference)),
            ("referenced_message", _reference_id(message.referenced_message)),
        ):
            if value:
                targets.append((field_name, str(value)))
        for target in message.message_link_targets:
            targets.append(("quoted_message_link", target))

        for field_name, target_id in targets:
            if target_id not in id_set or target_id == message.message_id:
                continue
            edge_type = "quoted_message_link" if field_name == "quoted_message_link" else "explicit_reply"
            confidence = 0.90 if edge_type == "quoted_message_link" else 1.0
            edges.append(
                EdgeRecord(
                    source_message_id=message.message_id,
                    target_message_id=target_id,
                    edge_type=edge_type,
                    confidence=confidence,
                    evidence={"source_field": field_name},
                    method="explicit",
                )
            )

    for native_thread_id, thread_messages in by_thread.items():
        thread_messages.sort(key=lambda message: message.timestamp)
        for previous, current in zip(thread_messages, thread_messages[1:], strict=False):
            if previous.message_id == current.message_id:
                continue
            edges.append(
                EdgeRecord(
                    source_message_id=current.message_id,
                    target_message_id=previous.message_id,
                    edge_type="native_thread",
                    confidence=0.95,
                    evidence={"native_thread_id": native_thread_id},
                    method="explicit",
                )
            )
    return _dedupe_edges(edges)


def generate_candidate_pairs(
    messages: list[MessageRecord],
    explicit_edges: list[EdgeRecord],
    threshold: float,
    uncertain_threshold: float,
    previous_message_window: int,
    time_window_hours: float,
    similarity_scan_limit: int,
    max_candidates_per_message: int,
) -> list[dict[str, Any]]:
    vectors = build_tfidf_vectors([message.tokens for message in messages])
    index_by_id = {message.message_id: index for index, message in enumerate(messages)}
    explicit_pairs = {
        (edge.source_message_id, edge.target_message_id): edge for edge in explicit_edges
    }
    author_to_indices: dict[str, list[int]] = defaultdict(list)
    native_thread_to_indices: dict[str, list[int]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    window_seconds = time_window_hours * 3600

    for source_index, source in enumerate(messages):
        candidates: dict[int, set[str]] = defaultdict(set)
        for target_index in range(max(0, source_index - previous_message_window), source_index):
            candidates[target_index].add("recent_message")

        for target_index in range(source_index - 1, -1, -1):
            delta = (source.timestamp - messages[target_index].timestamp).total_seconds()
            if delta > window_seconds:
                break
            candidates[target_index].add("within_24h")

        for mentioned_author in source.mentions:
            for target_index in author_to_indices.get(mentioned_author, [])[-100:]:
                candidates[target_index].add("source_mentions_target_author")

        for target_index in range(max(0, source_index - 200), source_index):
            target = messages[target_index]
            if source.author_id in target.mentions:
                candidates[target_index].add("target_mentions_source_author")

        if source.native_thread_id:
            for target_index in native_thread_to_indices.get(str(source.native_thread_id), []):
                candidates[target_index].add("same_native_thread")

        scan_start = max(0, source_index - similarity_scan_limit)
        for target_index in range(scan_start, source_index):
            target = messages[target_index]
            semantic = cosine_similarity(vectors[source_index], vectors[target_index])
            if semantic >= 0.12:
                candidates[target_index].add("text_similarity")
            if set(source.technical_tokens) & set(target.technical_tokens):
                candidates[target_index].add("shared_technical_tokens")

        for edge in explicit_edges:
            if edge.source_message_id == source.message_id and edge.target_message_id in index_by_id:
                candidates[index_by_id[edge.target_message_id]].add("explicit_edge")

        selected_indices = _limit_candidate_indices(
            source=source,
            messages=messages,
            candidates=candidates,
            max_candidates=max_candidates_per_message,
        )
        source_rows: list[dict[str, Any]] = []
        for target_index in selected_indices:
            target = messages[target_index]
            features = calculate_pair_features(
                source=source,
                target=target,
                source_vector=vectors[source_index],
                target_vector=vectors[target_index],
                source_index=source_index,
                target_index=target_index,
                messages=messages,
                explicit_edge=explicit_pairs.get((source.message_id, target.message_id)),
            )
            score = score_pair(features)
            row = {
                "source_message_id": source.message_id,
                "target_message_id": target.message_id,
                "candidate_reason_json": json.dumps(sorted(candidates[target_index]), ensure_ascii=False),
                **features,
                "score": score,
                "is_above_threshold": score >= threshold,
                "is_uncertain": threshold <= score < uncertain_threshold,
            }
            source_rows.append(row)

        source_rows.sort(key=lambda row: (-float(row["score"]), float(row["delta_seconds"])))
        for rank, row in enumerate(source_rows, start=1):
            row["candidate_rank"] = rank
        rows.extend(source_rows)
        author_to_indices[source.author_id or "unknown"].append(source_index)
        if source.native_thread_id:
            native_thread_to_indices[str(source.native_thread_id)].append(source_index)

    return rows


def calculate_pair_features(
    source: MessageRecord,
    target: MessageRecord,
    source_vector: dict[str, float],
    target_vector: dict[str, float],
    source_index: int,
    target_index: int,
    messages: list[MessageRecord],
    explicit_edge: EdgeRecord | None,
) -> dict[str, Any]:
    delta_seconds = max(0.0, (source.timestamp - target.timestamp).total_seconds())
    semantic_similarity = cosine_similarity(source_vector, target_vector)
    lexical = lexical_overlap(source.tokens, target.tokens)
    source_mentions_target = bool(target.author_id and target.author_id in source.mentions)
    target_mentions_source = bool(source.author_id and source.author_id in target.mentions)
    recent_start = max(0, source_index - 20)
    recent_authors = {message.author_id for message in messages[recent_start:source_index]}
    author_recent = bool(target.author_id and target.author_id in recent_authors)
    same_native_thread = bool(
        source.native_thread_id
        and target.native_thread_id
        and str(source.native_thread_id) == str(target.native_thread_id)
    )
    target_question = question_score(target.content_normalized)
    source_response = response_marker_score(source.content_normalized)
    question_answer = max(target_question * source_response, 0.35 if target_question and source_response else 0.0)
    mention_score = 1.0 if source_mentions_target else 0.75 if target_mentions_source else 0.0
    participant_continuity = min(
        1.0,
        (0.35 if source.author_id == target.author_id else 0.0)
        + (0.35 if author_recent else 0.0)
        + (0.30 if source_mentions_target or target_mentions_source else 0.0),
    )
    shared_urls = sorted(set(source.url_hosts) & set(target.url_hosts))
    shared_tech = sorted(set(source.technical_tokens) & set(target.technical_tokens))
    temporal_score = 1.0 / (1.0 + (delta_seconds / 1800.0))
    same_channel = source.channel_id == target.channel_id

    return {
        "delta_seconds": round(delta_seconds, 3),
        "log_delta_seconds": round(math.log1p(delta_seconds), 6),
        "temporal_score": round(temporal_score, 6),
        "same_burst": delta_seconds <= 300,
        "same_author": source.author_id == target.author_id,
        "source_mentions_target_author": source_mentions_target,
        "target_mentions_source_author": target_mentions_source,
        "author_participated_recently": author_recent,
        "semantic_similarity": round(semantic_similarity, 6),
        "lexical_overlap": round(lexical, 6),
        "shared_technical_tokens": json.dumps(shared_tech, ensure_ascii=False),
        "shared_technical_token_count": len(shared_tech),
        "technical_discussion_score": 1.0
        if shared_tech and (source_mentions_target or target_mentions_source or target_question > 0)
        else 0.0,
        "shared_url": bool(shared_urls),
        "shared_url_hosts": json.dumps(shared_urls, ensure_ascii=False),
        "shared_code_error_marker": bool(source.code_or_error_marker and target.code_or_error_marker),
        "target_has_question": target_question > 0,
        "source_looks_response": source_response > 0,
        "source_starts_response_marker": source_response >= 1.0,
        "source_disagreement_marker": bool(DISAGREEMENT_RE.search(source.content_normalized)),
        "source_reason_marker": bool(REASON_RE.search(source.content_normalized)),
        "source_second_person": bool(SECOND_PERSON_RE.search(source.content_normalized)),
        "question_answer_score": round(question_answer, 6),
        "explicit_reply": bool(explicit_edge and explicit_edge.edge_type == "explicit_reply"),
        "same_native_thread": same_native_thread,
        "same_channel": same_channel,
        "source_is_bot": source.is_bot,
        "target_is_bot": target.is_bot,
        "source_has_attachment": source.has_attachment,
        "target_has_attachment": target.has_attachment,
        "source_has_code_block": source.has_code_block,
        "target_has_code_block": target.has_code_block,
        "mention_score": round(mention_score, 6),
        "same_native_thread_score": 1.0 if same_native_thread else 0.0,
        "participant_continuity_score": round(participant_continuity, 6),
    }


def score_pair(features: dict[str, Any]) -> float:
    if features.get("explicit_reply"):
        return 1.0

    semantic_similarity = float(features.get("semantic_similarity", 0.0))
    temporal_score = float(features.get("temporal_score", 0.0))
    mention_score = float(features.get("mention_score", 0.0))
    lexical = float(features.get("lexical_overlap", 0.0))
    question_answer = float(features.get("question_answer_score", 0.0))
    same_native_thread = float(features.get("same_native_thread_score", 0.0))
    participant = float(features.get("participant_continuity_score", 0.0))
    technical_discussion = float(features.get("technical_discussion_score", 0.0))

    score = (
        0.30 * semantic_similarity
        + 0.20 * temporal_score
        + 0.15 * mention_score
        + 0.10 * lexical
        + 0.10 * question_answer
        + 0.10 * same_native_thread
        + 0.05 * participant
    )
    if same_native_thread:
        score += 0.08
    if technical_discussion:
        score += 0.10

    delta = float(features.get("delta_seconds", 0.0))
    if delta > 86400 and not same_native_thread and not mention_score:
        score *= 0.35
    elif delta > 21600 and not same_native_thread and not mention_score:
        score *= 0.75

    if semantic_similarity >= 0.5 and temporal_score < 0.15 and mention_score == 0 and participant < 0.25:
        score *= 0.5

    if (
        semantic_similarity < 0.15
        and lexical < 0.12
        and mention_score == 0
        and participant < 0.35
        and not same_native_thread
    ):
        score *= 0.70
    return round(min(max(score, 0.0), 1.0), 6)


def select_inferred_edges(
    candidate_pairs: list[dict[str, Any]],
    explicit_edges: list[EdgeRecord],
    threshold: float,
    uncertain_threshold: float,
) -> list[EdgeRecord]:
    explicit_sources = {edge.source_message_id for edge in explicit_edges}
    rows_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_pairs:
        if row["source_message_id"] not in explicit_sources:
            rows_by_source[row["source_message_id"]].append(row)

    edges: list[EdgeRecord] = []
    for source_id, rows in rows_by_source.items():
        rows.sort(key=lambda row: (-float(row["score"]), float(row["delta_seconds"])))
        if not rows:
            continue
        best = rows[0]
        best_score = float(best["score"])
        if best_score < threshold:
            continue
        alternatives = [
            {
                "message_id": row["target_message_id"],
                "score": row["score"],
                "delta_seconds": row["delta_seconds"],
            }
            for row in rows[1:4]
        ]
        close_alternative = bool(rows[1:2] and best_score - float(rows[1]["score"]) <= 0.08)
        edge_type = "uncertain" if best_score < uncertain_threshold or close_alternative else "inferred"
        evidence = _candidate_evidence(best)
        evidence["evidence_labels"] = evidence_labels(evidence)
        edges.append(
            EdgeRecord(
                source_message_id=source_id,
                target_message_id=best["target_message_id"],
                edge_type=edge_type,
                confidence=best_score,
                evidence=evidence,
                method="heuristic_v1",
                candidate_rank=1,
                alternative_parents=alternatives,
            )
        )
    return edges


def build_graph(messages: list[MessageRecord], edges: list[EdgeRecord]) -> nx.DiGraph:
    graph = nx.DiGraph()
    for message in messages:
        graph.add_node(
            message.message_id,
            author=message.author_anon,
            timestamp=message.timestamp_iso,
            channel_name=message.channel_name or "",
            native_thread_id=message.native_thread_id or "",
        )
    for edge in edges:
        graph.add_edge(
            edge.source_message_id,
            edge.target_message_id,
            edge_type=edge.edge_type,
            confidence=edge.confidence,
            method=edge.method,
        )
    return graph


def extract_threads(
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    split_gap_hours: float,
) -> list[ThreadRecord]:
    message_by_id = {message.message_id: message for message in messages}
    graph = nx.Graph()
    graph.add_nodes_from(message.message_id for message in messages)
    for edge in graph_edges:
        graph.add_edge(edge.source_message_id, edge.target_message_id)

    split_gap_seconds = split_gap_hours * 3600
    components: list[list[MessageRecord]] = []
    edge_lookup = {(edge.source_message_id, edge.target_message_id): edge for edge in graph_edges}
    edge_lookup.update({(edge.target_message_id, edge.source_message_id): edge for edge in graph_edges})

    for component in nx.connected_components(graph):
        ordered = sorted((message_by_id[message_id] for message_id in component), key=lambda msg: msg.timestamp)
        current_segment: list[MessageRecord] = []
        for message in ordered:
            if not current_segment:
                current_segment.append(message)
                continue
            previous = current_segment[-1]
            gap = (message.timestamp - previous.timestamp).total_seconds()
            connecting_edge = _find_edge_between_segment(message, current_segment, edge_lookup)
            explicit_bridge = connecting_edge and connecting_edge.edge_type in {
                "explicit_reply",
                "native_thread",
                "quoted_message_link",
            }
            if gap > split_gap_seconds and not explicit_bridge:
                components.append(current_segment)
                current_segment = [message]
            else:
                current_segment.append(message)
        if current_segment:
            components.append(current_segment)

    components.sort(key=lambda component: component[0].timestamp)
    threads: list[ThreadRecord] = []
    for index, component in enumerate(components, start=1):
        thread_id = f"T_{index:04d}"
        message_ids = [message.message_id for message in component]
        message_id_set = set(message_ids)
        internal_edges = [
            edge
            for edge in graph_edges
            if edge.source_message_id in message_id_set and edge.target_message_id in message_id_set
        ]
        root_message_id = _root_message_id(component, internal_edges)
        participants = sorted({message.author_anon or "USER_UNKNOWN" for message in component})
        confidences = [edge.confidence for edge in internal_edges]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 1.0
        explicit_count = sum(edge.edge_type in {"explicit_reply", "native_thread", "quoted_message_link"} for edge in internal_edges)
        inferred_count = sum(edge.edge_type == "inferred" for edge in internal_edges)
        uncertain_count = sum(edge.edge_type == "uncertain" for edge in internal_edges)
        keywords = extract_keywords(component)
        shape = conversation_shape(component, keywords)
        short_ratio = sum(len(message.tokens) <= 3 for message in component) / len(component)
        reasons: list[str] = []
        if avg_confidence < 0.60:
            reasons.append("low_avg_confidence")
        if uncertain_count:
            reasons.append("many_uncertain_edges")
        if len(component) == 1:
            reasons.append("single_message_thread")
        if len(component) >= 30:
            reasons.append("large_thread")
        if short_ratio > 0.50 and len(component) > 2:
            reasons.append("many_short_messages")
        for edge in internal_edges:
            if edge.edge_type in {"inferred", "uncertain"}:
                source = message_by_id[edge.source_message_id]
                target = message_by_id[edge.target_message_id]
                if (source.timestamp - target.timestamp).total_seconds() > split_gap_seconds:
                    reasons.append("large_temporal_gap")
                    break
        status = "ok"
        if reasons:
            status = "needs_review" if "single_message_thread" in reasons else "ambiguous"
        title = make_title(component, keywords)
        neutral_summary = make_neutral_summary(component, keywords)
        threads.append(
            ThreadRecord(
                thread_id=thread_id,
                root_message_id=root_message_id,
                message_ids=message_ids,
                participants=participants,
                start_time=component[0].timestamp,
                end_time=component[-1].timestamp,
                duration_seconds=(component[-1].timestamp - component[0].timestamp).total_seconds(),
                message_count=len(component),
                participant_count=len(participants),
                avg_confidence=round(avg_confidence, 6),
                explicit_edge_count=explicit_count,
                inferred_edge_count=inferred_count,
                uncertain_edge_count=uncertain_count,
                keywords=keywords,
                conversation_shape=shape,
                status=status,
                needs_review_reasons=sorted(set(reasons)),
                title=title,
                neutral_summary=neutral_summary,
            )
        )
    return threads


def assign_thread_ids(messages: list[MessageRecord], threads: list[ThreadRecord]) -> dict[str, str]:
    thread_by_message: dict[str, str] = {}
    for thread in threads:
        for message_id in thread.message_ids:
            thread_by_message[message_id] = thread.thread_id
    for message in messages:
        thread_by_message.setdefault(message.message_id, "T_UNASSIGNED")
    return thread_by_message


def build_thread_messages(
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    thread_by_message: dict[str, str],
) -> list[dict[str, Any]]:
    primary_edge = primary_edge_by_source(graph_edges)
    positions: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for message in sorted(messages, key=lambda item: item.timestamp):
        thread_id = thread_by_message[message.message_id]
        positions[thread_id] += 1
        edge = primary_edge.get(message.message_id)
        parent_id = ""
        parent_score: float | str = ""
        link_type = ""
        evidence: dict[str, Any] = {}
        alternatives: list[dict[str, Any]] = []
        if edge and thread_by_message.get(edge.target_message_id) == thread_id:
            parent_id = edge.target_message_id
            parent_score = edge.confidence
            link_type = edge.edge_type
            evidence = edge.evidence
            alternatives = edge.alternative_parents
        rows.append(
            {
                "thread_id": thread_id,
                "position": positions[thread_id],
                "message_id": message.message_id,
                "parent_message_id": parent_id,
                "parent_score": parent_score,
                "link_type": link_type,
                "evidence_json": json.dumps(evidence, ensure_ascii=False),
                "alternative_parents_json": json.dumps(alternatives, ensure_ascii=False),
                "author_id": message.author_anon,
                "timestamp": message.timestamp_iso,
                "content_normalized": message.content_normalized,
                "native_thread_id": message.native_thread_id or "",
                "has_attachment": message.has_attachment,
                "has_code_block": message.has_code_block,
                "has_url": message.has_url,
                "neutral_summary": "",
                "scd_summary": "",
                "incivility_label": "",
                "derailment_risk": "",
                "derailment_point": "",
                "tone_markers": "",
                "tension_triggers": "",
            }
        )
    return rows


def messages_to_dataframe(messages: list[MessageRecord], preserve_raw_content: bool) -> pd.DataFrame:
    rows = []
    for message in messages:
        rows.append(
            {
                "message_id": message.message_id,
                "guild_id": message.guild_id or "",
                "guild_name": message.guild_name or "",
                "channel_id": message.channel_id or "",
                "channel_name": message.channel_name or "",
                "native_thread_id": message.native_thread_id or "",
                "author_id": message.author_anon,
                "timestamp": message.timestamp_iso,
                "edited_timestamp": message.edited_timestamp or "",
                "content_raw": message.content_raw if preserve_raw_content else "",
                "content_normalized": message.content_normalized,
                "reply_to_message_id": message.reply_to_message_id or "",
                "message_reference_id": _reference_id(message.message_reference) or "",
                "referenced_message_id": _reference_id(message.referenced_message) or "",
                "mentions": json.dumps(message.mention_anons, ensure_ascii=False),
                "attachments": json.dumps(_safe_attachment_public(message.attachments), ensure_ascii=False),
                "embeds": json.dumps(message.embeds, ensure_ascii=False),
                "reactions": json.dumps(message.reactions, ensure_ascii=False),
                "is_bot": message.is_bot,
                "is_webhook": message.is_webhook,
                "message_type": message.message_type,
                "has_attachment": message.has_attachment,
                "has_code_block": message.has_code_block,
                "has_url": message.has_url,
                "url_hosts": json.dumps(message.url_hosts, ensure_ascii=False),
                "tokens": json.dumps(message.tokens, ensure_ascii=False),
                "technical_tokens": json.dumps(message.technical_tokens, ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def edges_to_dataframe(edges: list[EdgeRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_message_id": edge.source_message_id,
                "target_message_id": edge.target_message_id,
                "edge_type": edge.edge_type,
                "confidence": edge.confidence,
                "method": edge.method,
                "candidate_rank": edge.candidate_rank or "",
                "evidence_json": json.dumps(edge.evidence, ensure_ascii=False),
                "alternative_parents_json": json.dumps(edge.alternative_parents, ensure_ascii=False),
            }
            for edge in edges
        ],
        columns=[
            "source_message_id",
            "target_message_id",
            "edge_type",
            "confidence",
            "method",
            "candidate_rank",
            "evidence_json",
            "alternative_parents_json",
        ],
    )


def threads_to_dataframe(threads: list[ThreadRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "thread_id": thread.thread_id,
                "root_message_id": thread.root_message_id,
                "message_ids": json.dumps(thread.message_ids, ensure_ascii=False),
                "participants": json.dumps(thread.participants, ensure_ascii=False),
                "start_time": thread.start_time.isoformat().replace("+00:00", "Z"),
                "end_time": thread.end_time.isoformat().replace("+00:00", "Z"),
                "duration_seconds": thread.duration_seconds,
                "message_count": thread.message_count,
                "participant_count": thread.participant_count,
                "avg_confidence": thread.avg_confidence,
                "explicit_edge_count": thread.explicit_edge_count,
                "inferred_edge_count": thread.inferred_edge_count,
                "uncertain_edge_count": thread.uncertain_edge_count,
                "keywords": json.dumps(thread.keywords, ensure_ascii=False),
                "conversation_shape": thread.conversation_shape,
                "status": thread.status,
                "needs_review_reasons": json.dumps(thread.needs_review_reasons, ensure_ascii=False),
                "title": thread.title,
            }
            for thread in threads
        ]
    )


def thread_summaries_to_dataframe(threads: list[ThreadRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "thread_id": thread.thread_id,
                "title": thread.title,
                "neutral_summary": thread.neutral_summary,
                "scd_summary": "",
                "incivility_label": "",
                "derailment_risk": "",
            }
            for thread in threads
        ]
    )


def build_annotation_review(thread_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "thread_id": row["thread_id"],
            "message_id": row["message_id"],
            "current_parent_id": row["parent_message_id"],
            "suggested_parent_id": "",
            "annotator_parent_id": "",
            "review_status": "pending",
            "notes": "",
        }
        for row in thread_messages
    ]


def write_threads_json(
    threads: list[ThreadRecord],
    thread_messages: list[dict[str, Any]],
    output_path: Path,
) -> None:
    messages_by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in thread_messages:
        messages_by_thread[row["thread_id"]].append(row)
    payload = []
    for thread in threads:
        payload.append(
            {
                "thread_id": thread.thread_id,
                "root_message_id": thread.root_message_id,
                "participants": thread.participants,
                "start_time": thread.start_time.isoformat().replace("+00:00", "Z"),
                "end_time": thread.end_time.isoformat().replace("+00:00", "Z"),
                "duration_seconds": thread.duration_seconds,
                "message_count": thread.message_count,
                "participant_count": thread.participant_count,
                "avg_confidence": thread.avg_confidence,
                "explicit_edge_count": thread.explicit_edge_count,
                "inferred_edge_count": thread.inferred_edge_count,
                "uncertain_edge_count": thread.uncertain_edge_count,
                "keywords": thread.keywords,
                "conversation_shape": thread.conversation_shape,
                "status": thread.status,
                "needs_review_reasons": thread.needs_review_reasons,
                "title": thread.title,
                "neutral_summary": thread.neutral_summary,
                "scd_summary": None,
                "incivility_label": None,
                "derailment_risk": None,
                "messages": messages_by_thread[thread.thread_id],
            }
        )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_graph_exports(graph: nx.DiGraph, out_dir: Path) -> None:
    graphml_graph = nx.DiGraph()
    for node, attrs in graph.nodes(data=True):
        graphml_graph.add_node(node, **{key: str(value) for key, value in attrs.items()})
    for source, target, attrs in graph.edges(data=True):
        graphml_graph.add_edge(source, target, **{key: str(value) for key, value in attrs.items()})
    nx.write_graphml(graphml_graph, out_dir / "graph.graphml")
    payload = nx.node_link_data(graph)
    (out_dir / "graph.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_neo4j_exports(
    messages: list[MessageRecord],
    threads: list[ThreadRecord],
    graph_edges: list[EdgeRecord],
    thread_by_message: dict[str, str],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    users_path = output_dir / "neo4j_users.csv"
    threads_path = output_dir / "neo4j_threads.csv"
    messages_path = output_dir / "neo4j_messages.csv"
    authored_path = output_dir / "neo4j_authored_relationships.csv"
    belongs_to_path = output_dir / "neo4j_belongs_to_relationships.csv"
    replies_to_path = output_dir / "neo4j_replies_to_relationships.csv"
    output_path = output_dir / "neo4j_import.cypher"

    user_ids = sorted({message.author_anon or "USER_UNKNOWN" for message in messages})
    with users_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["user_id"])
        writer.writeheader()
        for user_id in user_ids:
            writer.writerow({"user_id": user_id})

    with threads_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["thread_id", "title", "status", "avg_confidence"],
        )
        writer.writeheader()
        for thread in threads:
            writer.writerow(
                {
                    "thread_id": thread.thread_id,
                    "title": thread.title,
                    "status": thread.status,
                    "avg_confidence": thread.avg_confidence,
                }
            )

    with messages_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "message_id",
                "author_id",
                "thread_id",
                "timestamp",
                "content",
                "channel_name",
                "guild_name",
                "has_attachment",
                "has_code_block",
                "has_url",
                "code_or_error_marker",
            ],
        )
        writer.writeheader()
        for message in messages:
            writer.writerow(
                {
                    "message_id": message.message_id,
                    "author_id": message.author_anon or "USER_UNKNOWN",
                    "thread_id": thread_by_message.get(message.message_id, "T_UNASSIGNED"),
                    "timestamp": message.timestamp_iso,
                    "content": message.content_normalized,
                    "channel_name": message.channel_name or "",
                    "guild_name": message.guild_name or message.guild_id or "",
                    "has_attachment": str(bool(message.has_attachment)).lower(),
                    "has_code_block": str(bool(message.has_code_block)).lower(),
                    "has_url": str(bool(message.has_url)).lower(),
                    "code_or_error_marker": str(bool(message.code_or_error_marker)).lower(),
                }
            )

    with authored_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["user_id", "message_id"])
        writer.writeheader()
        for message in messages:
            writer.writerow(
                {
                    "user_id": message.author_anon or "USER_UNKNOWN",
                    "message_id": message.message_id,
                }
            )

    with belongs_to_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["message_id", "thread_id"])
        writer.writeheader()
        for message in messages:
            writer.writerow(
                {
                    "message_id": message.message_id,
                    "thread_id": thread_by_message.get(message.message_id, "T_UNASSIGNED"),
                }
            )

    with replies_to_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_message_id", "target_message_id", "confidence", "method", "edge_type"],
        )
        writer.writeheader()
        for edge in graph_edges:
            writer.writerow(
                {
                    "source_message_id": edge.source_message_id,
                    "target_message_id": edge.target_message_id,
                    "confidence": edge.confidence,
                    "method": edge.method,
                    "edge_type": edge.edge_type,
                }
            )

    lines = [
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;",
        "CREATE CONSTRAINT message_id IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE;",
        "CREATE CONSTRAINT thread_id IF NOT EXISTS FOR (t:Thread) REQUIRE t.id IS UNIQUE;",
        "",
        "// Copie os CSVs deste diretório para a pasta import/ do Neo4j antes de executar este script.",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_users.csv' AS row",
        "MERGE (u:User {id: row.user_id});",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_threads.csv' AS row",
        "MERGE (t:Thread {id: row.thread_id})",
        "SET t.title = row.title,",
        "    t.status = row.status,",
        "    t.avg_confidence = toFloat(row.avg_confidence);",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_messages.csv' AS row",
        "MERGE (m:Message {id: row.message_id})",
        "SET m.timestamp = datetime(row.timestamp),",
        "    m.content = row.content,",
        "    m.channel_name = row.channel_name,",
        "    m.guild_name = row.guild_name,",
        "    m.has_attachment = toBoolean(row.has_attachment),",
        "    m.has_code_block = toBoolean(row.has_code_block),",
        "    m.has_url = toBoolean(row.has_url),",
        "    m.code_or_error_marker = toBoolean(row.code_or_error_marker);",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_authored_relationships.csv' AS row",
        "MATCH (u:User {id: row.user_id}), (m:Message {id: row.message_id})",
        "MERGE (u)-[:AUTHORED]->(m);",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_belongs_to_relationships.csv' AS row",
        "MATCH (m:Message {id: row.message_id}), (t:Thread {id: row.thread_id})",
        "MERGE (m)-[:BELONGS_TO]->(t);",
        "",
        "LOAD CSV WITH HEADERS FROM 'file:///neo4j_replies_to_relationships.csv' AS row",
        "MATCH (s:Message {id: row.source_message_id}), (t:Message {id: row.target_message_id})",
        "MERGE (s)-[r:REPLIES_TO]->(t)",
        "SET r.confidence = toFloat(row.confidence),",
        "    r.method = row.method,",
        "    r.edge_type = row.edge_type;",
        "",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def suggest_merges(threads: list[ThreadRecord]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    ordered = sorted(threads, key=lambda thread: thread.start_time)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        gap = (current.start_time - previous.end_time).total_seconds()
        keyword_overlap = set(previous.keywords) & set(current.keywords)
        if 0 <= gap <= 1800 and keyword_overlap and (
            previous.status != "ok" or current.status != "ok" or previous.message_count <= 2 or current.message_count <= 2
        ):
            suggestions.append(
                {
                    "left_thread_id": previous.thread_id,
                    "right_thread_id": current.thread_id,
                    "gap_seconds": gap,
                    "shared_keywords": sorted(keyword_overlap),
                    "reason": "possible_over_split",
                }
            )
    return suggestions


def extract_keywords(messages: list[MessageRecord], limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    for message in messages:
        counts.update(message.technical_tokens)
        counts.update(token for token in message.tokens if len(token) > 3)
    return [token for token, _count in counts.most_common(limit)]


def conversation_shape(messages: list[MessageRecord], keywords: list[str]) -> str:
    if len(messages) <= 2:
        return "thread_curta"
    has_question = any(question_score(message.content_normalized) > 0 for message in messages)
    has_response = any(response_marker_score(message.content_normalized) > 0 for message in messages)
    if has_question and has_response:
        return "pergunta_resposta"
    if keywords and any(keyword in {"neo4j", "cypher", "query", "driver", "database", "graph"} for keyword in keywords):
        return "discussao_tecnica"
    social_markers = ("kkk", "haha", "valeu", "obrigado", "bom dia")
    if any(marker in message.content_normalized.lower() for message in messages for marker in social_markers):
        return "conversa_social"
    if len(messages) >= 3:
        return "sequencia_informativa"
    return "ambigua"


def make_title(messages: list[MessageRecord], keywords: list[str]) -> str:
    first = messages[0].content_normalized.strip()
    if first:
        compact = " ".join(first.split())
        return compact[:90] + ("..." if len(compact) > 90 else "")
    if keywords:
        return " / ".join(keywords[:4])
    return messages[0].message_id


def make_neutral_summary(messages: list[MessageRecord], keywords: list[str]) -> str:
    keyword_text = ", ".join(keywords[:5]) if keywords else "sem palavras-chave fortes"
    return (
        f"{len(messages)} mensagens entre {len({message.author_anon for message in messages})} "
        f"participantes; termos principais: {keyword_text}."
    )


def primary_edge_by_source(graph_edges: list[EdgeRecord]) -> dict[str, EdgeRecord]:
    priority = {
        "explicit_reply": 5,
        "native_thread": 4,
        "quoted_message_link": 3,
        "inferred": 2,
        "uncertain": 1,
    }
    primary: dict[str, EdgeRecord] = {}
    for edge in graph_edges:
        current = primary.get(edge.source_message_id)
        if current is None:
            primary[edge.source_message_id] = edge
            continue
        key = (priority.get(edge.edge_type, 0), edge.confidence)
        current_key = (priority.get(current.edge_type, 0), current.confidence)
        if key > current_key:
            primary[edge.source_message_id] = edge
    return primary


def _matches_scope(
    row: dict[str, Any],
    guild_name: str | None,
    guild_id: str | None,
    channel_name: str | None,
    channel_id: str | None,
) -> bool:
    if guild_id and str(row.get("guild_id") or "") != str(guild_id):
        return False
    if guild_name and str(row.get("guild_name") or "").casefold() != guild_name.casefold():
        return False
    if channel_id and str(row.get("channel_id") or "") == str(channel_id):
        return True
    if channel_name:
        return str(row.get("channel_name") or "").casefold() == channel_name.casefold()
    return True


def _mention_ids(value: Any) -> list[str]:
    if not value:
        return []
    mentions = value if isinstance(value, list) else [value]
    ids: list[str] = []
    for mention in mentions:
        if isinstance(mention, dict):
            value = mention.get("id") or mention.get("user_id")
        else:
            value = mention
        if value not in (None, ""):
            ids.append(str(value))
    return _dedupe(ids)


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _safe_attachment_public(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for attachment in attachments:
        safe.append(
            {
                "filename": attachment.get("filename") or attachment.get("name") or "",
                "content_type": attachment.get("content_type") or attachment.get("type") or "",
                "size": attachment.get("size") or "",
            }
        )
    return safe


def _reference_id(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value if value.isdigit() or value.startswith("m_") else None
    if isinstance(value, dict):
        for key in ("message_id", "messageId", "id"):
            if value.get(key):
                return str(value[key])
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _dedupe_edges(edges: list[EdgeRecord]) -> list[EdgeRecord]:
    best: dict[tuple[str, str, str], EdgeRecord] = {}
    for edge in edges:
        key = (edge.source_message_id, edge.target_message_id, edge.edge_type)
        if key not in best or edge.confidence > best[key].confidence:
            best[key] = edge
    return sorted(
        best.values(),
        key=lambda edge: (edge.source_message_id, -edge.confidence, edge.target_message_id),
    )


def _limit_candidate_indices(
    source: MessageRecord,
    messages: list[MessageRecord],
    candidates: dict[int, set[str]],
    max_candidates: int,
) -> list[int]:
    if len(candidates) <= max_candidates:
        return sorted(candidates)
    ranked = sorted(
        candidates,
        key=lambda index: (
            -len(candidates[index]),
            (source.timestamp - messages[index].timestamp).total_seconds(),
        ),
    )
    return sorted(ranked[:max_candidates])


def _candidate_evidence(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "delta_seconds",
        "semantic_similarity",
        "temporal_score",
        "mention_score",
        "lexical_overlap",
        "question_answer_score",
        "same_native_thread_score",
        "participant_continuity_score",
        "shared_technical_token_count",
        "technical_discussion_score",
        "shared_url",
        "shared_code_error_marker",
        "candidate_rank",
        "candidate_reason_json",
    ]
    evidence = {key: row.get(key) for key in keys}
    evidence["score_formula"] = (
        "0.30*semantic_similarity + 0.20*temporal_score + 0.15*mention_score "
        "+ 0.10*lexical_overlap + 0.10*question_answer_score "
        "+ 0.10*same_native_thread_score + 0.05*participant_continuity_score; "
        "rules: +0.08 same_native_thread, +0.10 technical_discussion, temporal/semantic penalties"
    )
    return evidence


def _find_edge_between_segment(
    message: MessageRecord,
    segment: list[MessageRecord],
    edge_lookup: dict[tuple[str, str], EdgeRecord],
) -> EdgeRecord | None:
    for previous in reversed(segment):
        edge = edge_lookup.get((message.message_id, previous.message_id))
        if edge:
            return edge
    return None


def _root_message_id(component: list[MessageRecord], internal_edges: list[EdgeRecord]) -> str:
    child_ids = {edge.source_message_id for edge in internal_edges}
    for message in component:
        if message.message_id not in child_ids:
            return message.message_id
    return component[0].message_id
