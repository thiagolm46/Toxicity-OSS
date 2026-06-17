from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from discord_disentanglement.io import load_discord_export
from discord_disentanglement.pipeline import (
    DisentanglementConfig,
    build_graph,
    extract_explicit_edges,
    extract_threads,
    generate_candidate_pairs,
    normalize_messages,
    run_pipeline,
    score_pair,
)
from discord_disentanglement.text import extract_url_hosts


def synthetic_messages() -> list[dict[str, object]]:
    return [
        {
            "message_id": "m_001",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u1",
            "timestamp": "2026-01-01T10:00:00Z",
            "content": "Como faco relacionamento many-to-many no Neo4J?",
        },
        {
            "message_id": "m_002",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u3",
            "timestamp": "2026-01-01T10:01:00Z",
            "content": "Meu docker do Neo4J nao sobe na porta 7474",
        },
        {
            "message_id": "m_003",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u2",
            "timestamp": "2026-01-01T10:02:00Z",
            "content": "<@u1> voce pode criar um no intermediario com duas relationships",
            "mentions": [{"id": "u1"}],
            "message_reference": {"message_id": "m_001"},
        },
        {
            "message_id": "m_004",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u4",
            "timestamp": "2026-01-01T10:03:00Z",
            "content": "<@u3> tenta docker compose logs porque parece erro de binding",
            "mentions": [{"id": "u3"}],
        },
        {
            "message_id": "m_005",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u1",
            "timestamp": "2026-01-01T10:04:00Z",
            "content": "isso?",
            "message_reference": {"message_id": "m_003"},
        },
        {
            "message_id": "m_006",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u3",
            "timestamp": "2026-01-01T10:05:00Z",
            "content": "valeu",
        },
        {
            "message_id": "m_007",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u2",
            "timestamp": "2026-01-02T18:00:00Z",
            "content": "sobre cypher, match retorna outro plano agora",
        },
        {
            "message_id": "m_008",
            "guild_id": "g1",
            "guild_name": "Neo4j",
            "channel_id": "c1",
            "channel_name": "Neo4J",
            "author_id": "u5",
            "timestamp": "2026-01-02T18:01:00Z",
            "content": "Alguem sabe criar index composto no Neo4J?",
        },
        {
            "message_id": "m_999",
            "guild_id": "g1",
            "guild_name": "Other Guild",
            "channel_id": "c2",
            "channel_name": "general",
            "author_id": "u9",
            "timestamp": "2026-01-01T10:00:00Z",
            "content": "fora do canal",
        },
    ]


def write_json(path: Path) -> None:
    path.write_text(json.dumps({"messages": synthetic_messages()}), encoding="utf-8")


def write_csv(path: Path) -> None:
    rows = synthetic_messages()
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = {
                key: json.dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(serialized)


def write_parquet(path: Path) -> None:
    rows = []
    for row in synthetic_messages():
        parquet_row = dict(row)
        if "message_reference" in parquet_row and isinstance(parquet_row["message_reference"], dict):
            parquet_row["referenced_message_id"] = parquet_row["message_reference"]["message_id"]
            del parquet_row["message_reference"]
        if "mentions" in parquet_row:
            parquet_row["mentions_json"] = json.dumps(parquet_row["mentions"])
            del parquet_row["mentions"]
        parquet_row["attachments_json"] = "[]"
        parquet_row["embeds_json"] = "[]"
        rows.append(parquet_row)
    pd.DataFrame(rows).to_parquet(path, index=False)


def test_load_json_and_csv(tmp_path: Path) -> None:
    json_path = tmp_path / "export.json"
    csv_path = tmp_path / "export.csv"
    write_json(json_path)
    write_csv(csv_path)

    assert len(load_discord_export(json_path)) == 9
    assert len(load_discord_export(csv_path)) == 9
    assert len(load_discord_export(json_path, guild_name="Neo4j")) == 8


def test_load_parquet_filters_guild_and_preserves_references(tmp_path: Path) -> None:
    parquet_path = tmp_path / "messages.parquet"
    write_parquet(parquet_path)

    rows = load_discord_export(parquet_path, guild_name="Neo4j")
    messages = normalize_messages(
        rows,
        guild_name="Neo4j",
        guild_id=None,
        channel_name=None,
        channel_id=None,
        preserve_raw_content=False,
    )
    explicit_edges = extract_explicit_edges(messages)

    assert len(rows) == 8
    assert {message.channel_name for message in messages} == {"Neo4J"}
    assert ("m_003", "m_001", "explicit_reply") in {
        (edge.source_message_id, edge.target_message_id, edge.edge_type)
        for edge in explicit_edges
    }


def test_normalize_anonymizes_users_and_extracts_explicit_reply(tmp_path: Path) -> None:
    json_path = tmp_path / "export.json"
    write_json(json_path)
    rows = load_discord_export(json_path)
    messages = normalize_messages(
        rows,
        guild_name="Neo4j",
        guild_id=None,
        channel_name="Neo4J",
        channel_id=None,
        preserve_raw_content=False,
    )

    assert len(messages) == 8
    assert messages[0].author_anon == "USER_001"
    assert "USER_001" in messages[2].content_normalized
    assert "u1" not in messages[2].content_normalized

    edges = extract_explicit_edges(messages)
    explicit = {(edge.source_message_id, edge.target_message_id, edge.edge_type) for edge in edges}
    assert ("m_003", "m_001", "explicit_reply") in explicit
    assert ("m_005", "m_003", "explicit_reply") in explicit


def test_candidate_generation_and_score(tmp_path: Path) -> None:
    json_path = tmp_path / "export.json"
    write_json(json_path)
    messages = normalize_messages(load_discord_export(json_path), "Neo4j", None, "Neo4J", None, False)
    explicit_edges = extract_explicit_edges(messages)
    candidates = generate_candidate_pairs(
        messages=messages,
        explicit_edges=explicit_edges,
        threshold=0.5,
        uncertain_threshold=0.6,
        previous_message_window=50,
        time_window_hours=24,
        similarity_scan_limit=250,
        max_candidates_per_message=150,
    )

    docker_pair = next(
        row for row in candidates if row["source_message_id"] == "m_004" and row["target_message_id"] == "m_002"
    )
    assert docker_pair["mention_score"] > 0
    assert docker_pair["score"] >= 0.5

    assert score_pair({"explicit_reply": True}) == 1.0


def test_short_same_channel_follow_up_gets_local_continuity_boost(tmp_path: Path) -> None:
    messages = {
        "messages": [
            {
                "message_id": "m_001",
                "guild_id": "g1",
                "guild_name": "Neo4j",
                "channel_id": "c1",
                "channel_name": "help-others",
                "author_id": "u1",
                "timestamp": "2026-01-01T10:00:00Z",
                "content": "You do not have the permission to view the message of #rules",
            },
            {
                "message_id": "m_002",
                "guild_id": "g1",
                "guild_name": "Neo4j",
                "channel_id": "c1",
                "channel_name": "help-others",
                "author_id": "u2",
                "timestamp": "2026-01-01T10:04:40Z",
                "content": "lemme look",
            },
            {
                "message_id": "m_003",
                "guild_id": "g1",
                "guild_name": "Neo4j",
                "channel_id": "c1",
                "channel_name": "help-others",
                "author_id": "u2",
                "timestamp": "2026-01-01T10:05:22Z",
                "content": "try now",
            },
        ]
    }
    input_path = tmp_path / "burst.json"
    input_path.write_text(json.dumps(messages), encoding="utf-8")

    normalized = normalize_messages(
        load_discord_export(input_path),
        guild_name="Neo4j",
        guild_id=None,
        channel_name="help-others",
        channel_id=None,
        preserve_raw_content=False,
    )
    candidates = generate_candidate_pairs(
        messages=normalized,
        explicit_edges=[],
        threshold=0.5,
        uncertain_threshold=0.6,
        previous_message_window=50,
        time_window_hours=24,
        similarity_scan_limit=250,
        max_candidates_per_message=150,
    )

    follow_up_pair = next(
        row for row in candidates if row["source_message_id"] == "m_003" and row["target_message_id"] == "m_002"
    )
    best_score = max(row["score"] for row in candidates if row["source_message_id"] == "m_003")

    assert follow_up_pair["same_channel_burst_score"] >= 0.85
    assert follow_up_pair["score"] == best_score
    assert follow_up_pair["score"] >= 0.5


def test_graph_threads_and_pipeline_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "export.json"
    out_dir = tmp_path / "neo4j_threads"
    write_json(input_path)

    outputs = run_pipeline(
        DisentanglementConfig(
            input_path=input_path,
            out_dir=out_dir,
            guild_name="Neo4j",
            channel_name="Neo4J",
            threshold=0.5,
        )
    )

    expected = [
        "messages_normalized.csv",
        "edges_explicit.csv",
        "candidate_pairs.csv",
        "edges_inferred.csv",
        "graph_edges.csv",
        "threads.csv",
        "threads.json",
        "thread_messages.csv",
        "thread_summaries.csv",
        "annotation_review.csv",
        "graph.graphml",
        "graph.json",
        "reports/neo4j_threads.html",
        "reports/neo4j_threads_summary.md",
        "exports/neo4j_users.csv",
        "exports/neo4j_threads.csv",
        "exports/neo4j_messages.csv",
        "exports/neo4j_authored_relationships.csv",
        "exports/neo4j_belongs_to_relationships.csv",
        "exports/neo4j_replies_to_relationships.csv",
        "exports/neo4j_import.cypher",
    ]
    for relative in expected:
        assert (out_dir / relative).exists(), relative

    messages_df = pd.read_csv(outputs["messages"])
    assert set(messages_df["author_id"]).issubset({"USER_001", "USER_002", "USER_003", "USER_004", "USER_005"})
    assert messages_df["content_raw"].fillna("").eq("").all()

    edges_df = pd.read_csv(outputs["graph_edges"])
    assert {"m_003", "m_005"}.issubset(set(edges_df["source_message_id"]))

    threads_df = pd.read_csv(outputs["threads"])
    assert len(threads_df) >= 2
    assert {"scd_summary", "incivility_label", "derailment_risk"}.issubset(
        set(pd.read_csv(outputs["thread_summaries"]).columns)
    )

    html = (out_dir / "reports" / "neo4j_threads.html").read_text(encoding="utf-8")
    assert "Neo4j Threads" in html
    assert "Cobertura dos dados" in html
    assert "Filtrar por canal" in html
    assert "incivility_label" in html

    cypher = (out_dir / "exports" / "neo4j_import.cypher").read_text(encoding="utf-8")
    assert "LOAD CSV WITH HEADERS FROM 'file:///neo4j_messages.csv'" in cypher
    assert "MERGE (s)-[r:REPLIES_TO]->(t)" in cypher


def test_extract_url_hosts_skips_malformed_ipv6_urls() -> None:
    text = "valid https://example.com/path broken http://[oops"

    assert extract_url_hosts(text) == ["example.com"]


def test_build_graph_and_extract_threads_directly(tmp_path: Path) -> None:
    json_path = tmp_path / "export.json"
    write_json(json_path)
    messages = normalize_messages(load_discord_export(json_path), "Neo4j", None, "Neo4J", None, False)
    explicit_edges = extract_explicit_edges(messages)
    graph = build_graph(messages, explicit_edges)
    threads = extract_threads(messages, explicit_edges, split_gap_hours=6)

    assert graph.number_of_nodes() == 8
    assert graph.number_of_edges() >= 2
    assert any(thread.message_count >= 2 for thread in threads)

