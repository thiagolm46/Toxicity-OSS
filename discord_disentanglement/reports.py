from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .models import EdgeRecord, MessageRecord, ThreadRecord
from .text import html_escape


def generate_main_html_report(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    thread_messages: list[dict[str, Any]],
    candidate_pairs: list[dict[str, Any]],
    output_path: Path,
) -> None:
    payload = build_report_payload(threads, messages, graph_edges, thread_messages, candidate_pairs)
    html = SIMPLE_REPORT_TEMPLATE.replace(
        "__REPORT_DATA__",
        json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
    )
    output_path.write_text(html, encoding="utf-8")


def generate_thread_graph_reports(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    output_dir: Path,
) -> None:
    for old_report in output_dir.glob("*.html"):
        old_report.unlink()

    message_by_id = {message.message_id: message for message in messages}
    thread_by_message: dict[str, str] = {}
    for thread in threads:
        for message_id in thread.message_ids:
            thread_by_message[message_id] = thread.thread_id

    edges_by_thread: dict[str, list[EdgeRecord]] = defaultdict(list)
    for edge in graph_edges:
        source_thread = thread_by_message.get(edge.source_message_id)
        if source_thread and source_thread == thread_by_message.get(edge.target_message_id):
            edges_by_thread[source_thread].append(edge)

    for thread in threads:
      channel_profile = _thread_channel_profile(thread, message_by_id)
      rows = []
      for index, message_id in enumerate(thread.message_ids, start=1):
        message = message_by_id[message_id]
        rows.append(
          {
            "position": index,
            "message_id": message.message_id,
            "author": message.author_anon,
            "channel": message.channel_name or "unknown",
            "timestamp": message.timestamp_iso,
            "content": message.content_normalized,
          }
        )
      links = [
        {
          "source": edge.source_message_id,
          "target": edge.target_message_id,
          "type": edge.edge_type,
          "confidence": edge.confidence,
          "method": edge.method,
          "evidence": compact_evidence(edge.evidence),
        }
        for edge in sorted(
          edges_by_thread[thread.thread_id],
          key=lambda item: (item.source_message_id, item.target_message_id),
        )
      ]
      payload = {
        "thread": {
          **thread_payload(thread),
          **channel_profile,
        },
        "messages": rows,
        "links": links,
      }
      html = THREAD_DETAIL_TEMPLATE.replace(
        "__THREAD_DATA__",
        json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
      )
      (output_dir / f"{thread.thread_id}.html").write_text(html, encoding="utf-8")


def generate_summary_markdown(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    merge_suggestions: list[dict[str, Any]],
    output_path: Path,
) -> None:
    sizes = [thread.message_count for thread in threads]
    explicit = sum(
        edge.edge_type in {"explicit_reply", "native_thread", "quoted_message_link"}
        for edge in graph_edges
    )
    inferred = sum(edge.edge_type in {"inferred", "inferred_reply"} for edge in graph_edges)
    uncertain = sum(edge.edge_type in {"uncertain", "uncertain_reply"} for edge in graph_edges)
    total_edges = len(graph_edges) or 1
    status_counts = Counter(thread.status for thread in threads)
    channel_counts = Counter(message.channel_name or "unknown" for message in messages)
    guild_counts = Counter(message.guild_name or message.guild_id or "unknown" for message in messages)

    lines = [
        "# Neo4j conversation disentanglement summary",
        "",
        "## Data coverage",
        "",
        f"- Input messages processed: {len(messages)}",
        "- This report only uses messages present in the input file.",
        "- If the count looks low, inspect the upstream extraction/parquet, not only this disentanglement step.",
        "- Guilds: "
        + ", ".join(f"{guild}={count}" for guild, count in guild_counts.most_common()),
        "- Channels: "
        + ", ".join(f"{channel}={count}" for channel, count in channel_counts.most_common()),
        "",
        "## Thread metrics",
        "",
        f"- Threads: {len(threads)}",
        f"- Avg messages/thread: {(sum(sizes) / len(sizes)) if sizes else 0:.2f}",
        f"- Median messages/thread: {_median(sizes):.2f}",
        f"- Single-message threads: {sum(size == 1 for size in sizes)}",
        f"- Short threads (<=2 messages): {sum(size <= 2 for size in sizes)}",
        f"- Long threads (>=15 messages): {sum(size >= 15 for size in sizes)}",
        f"- Ambiguous/needs review: {status_counts.get('ambiguous', 0) + status_counts.get('needs_review', 0)}",
        f"- Explicit links: {explicit} ({explicit / total_edges:.1%})",
        f"- Inferred links: {inferred} ({inferred / total_edges:.1%})",
        f"- Uncertain links: {uncertain} ({uncertain / total_edges:.1%})",
        f"- Overall avg confidence: {_avg([thread.avg_confidence for thread in threads]):.3f}",
        "",
        "## Review reasons",
        "",
    ]
    reason_counts = Counter(reason for thread in threads for reason in thread.needs_review_reasons)
    if reason_counts:
        lines.extend(f"- {reason}: {count}" for reason, count in reason_counts.most_common())
    else:
        lines.append("- none")

    lines.extend(["", "## Suggested merges (non destructive)", ""])
    if merge_suggestions:
        for suggestion in merge_suggestions[:100]:
            lines.append(
                "- "
                f"{suggestion['left_thread_id']} + {suggestion['right_thread_id']} "
                f"gap={suggestion['gap_seconds']:.0f}s "
                f"keywords={', '.join(suggestion['shared_keywords'])}"
            )
        if len(merge_suggestions) > 100:
            lines.append(f"- ... {len(merge_suggestions) - 100} more suggestions omitted")
    else:
        lines.append("- none")

    lines.extend(["", "## Notes", ""])
    lines.append("- Incivility, SCD and derailment fields are placeholders only.")
    lines.append("- User identifiers are anonymized as USER_XXX in generated reports.")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report_payload(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    thread_messages: list[dict[str, Any]],
    candidate_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
  message_by_id = {message.message_id: message for message in messages}
  edge_by_source = {edge.source_message_id: edge for edge in graph_edges}
  candidate_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for row in candidate_pairs:
    candidate_by_source[row["source_message_id"]].append(row)
  for rows in candidate_by_source.values():
    rows.sort(key=lambda item: int(item.get("candidate_rank") or 999))

  messages_by_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for row in thread_messages:
    message = message_by_id[row["message_id"]]
    edge = edge_by_source.get(row["message_id"])
    messages_by_thread[row["thread_id"]].append(
      {
        "position": int(row["position"]),
        "message_id": row["message_id"],
        "author": row["author_id"],
        "channel": message.channel_name or "unknown",
        "timestamp": row["timestamp"],
        "content": row["content_normalized"],
        "parent_message_id": row["parent_message_id"],
        "parent_score": row["parent_score"],
        "link_type": row["link_type"],
        "evidence": compact_evidence(edge.evidence if edge else {}),
        "alternatives": compact_alternatives(edge.alternative_parents if edge else []),
      }
    )

  thread_payloads = []
  for thread in threads:
    channel_profile = _thread_channel_profile(thread, message_by_id)
    thread_payloads.append(
      {
        **thread_payload(thread),
        **channel_profile,
        "messages": messages_by_thread[thread.thread_id],
        "detail_url": f"thread_graphs/{thread.thread_id}.html",
      }
    )

  channel_counts = Counter(message.channel_name or "unknown" for message in messages)
  guild_counts = Counter(message.guild_name or message.guild_id or "unknown" for message in messages)
  edge_counts = Counter(edge.edge_type for edge in graph_edges)
  sizes = [thread.message_count for thread in threads]
  status_counts = Counter(thread.status for thread in threads)

  return {
    "coverage": {
      "message_count": len(messages),
      "thread_count": len(threads),
      "guild_counts": dict(guild_counts.most_common()),
      "channel_counts": dict(channel_counts.most_common()),
      "first_message_at": min((message.timestamp_iso for message in messages), default=""),
      "last_message_at": max((message.timestamp_iso for message in messages), default=""),
      "note": (
        "This report only uses messages present in the input file. "
        "If the count seems low, inspect the upstream extraction/parquet."
      ),
    },
    "metrics": {
      "avg_messages_per_thread": _avg([float(size) for size in sizes]),
      "median_messages_per_thread": _median(sizes),
      "single_message_threads": sum(size == 1 for size in sizes),
      "short_threads": sum(size <= 2 for size in sizes),
      "long_threads": sum(size >= 15 for size in sizes),
      "ok_threads": status_counts.get("ok", 0),
      "ambiguous_threads": status_counts.get("ambiguous", 0),
      "needs_review_threads": status_counts.get("needs_review", 0),
      "explicit_edges": sum(
        edge_counts.get(edge_type, 0)
        for edge_type in ("explicit_reply", "native_thread", "quoted_message_link")
      ),
      "inferred_edges": edge_counts.get("inferred", 0) + edge_counts.get("inferred_reply", 0),
      "uncertain_edges": edge_counts.get("uncertain", 0) + edge_counts.get("uncertain_reply", 0),
    },
    "threads": thread_payloads,
  }


def thread_payload(thread: ThreadRecord) -> dict[str, Any]:
    return {
        "thread_id": thread.thread_id,
        "title": thread.title,
        "root_message_id": thread.root_message_id,
        "start_time": thread.start_time.isoformat(),
        "end_time": thread.end_time.isoformat(),
        "duration_seconds": thread.duration_seconds,
        "message_count": thread.message_count,
        "participant_count": thread.participant_count,
        "participants": thread.participants,
        "avg_confidence": thread.avg_confidence,
        "min_confidence": thread.min_confidence,
        "explicit_edge_count": thread.explicit_edge_count,
        "inferred_edge_count": thread.inferred_edge_count,
        "uncertain_edge_count": thread.uncertain_edge_count,
        "keywords": thread.keywords,
        "conversation_shape": thread.conversation_shape,
        "status": thread.status,
        "needs_review_reasons": thread.needs_review_reasons,
        "neutral_summary": thread.neutral_summary,
        "scd_summary": None,
        "incivility_label": None,
        "derailment_risk": None,
    }


def _thread_channel_profile(
    thread: ThreadRecord,
    message_by_id: dict[str, MessageRecord],
) -> dict[str, Any]:
    channel_counts = Counter(
        message_by_id[message_id].channel_name or "unknown"
        for message_id in thread.message_ids
        if message_id in message_by_id
    )
    ordered_channels = [channel for channel, _count in channel_counts.most_common()]
    primary_channel = ordered_channels[0] if ordered_channels else "unknown"
    return {
        "primary_channel": primary_channel,
        "channel_names": ordered_channels,
        "channel_counts": dict(channel_counts),
        "multi_channel": len(ordered_channels) > 1,
    }


def compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not evidence:
        return {}
    keys = [
        "delta_seconds",
        "semantic_similarity",
        "temporal_score",
        "mention_score",
        "lexical_overlap",
        "question_answer_score",
        "same_native_thread_score",
        "participant_continuity_score",
        "same_channel_burst_score",
        "shared_technical_token_count",
        "technical_discussion_score",
        "evidence_labels",
    ]
    return {key: evidence[key] for key in keys if key in evidence}


def compact_alternatives(alternatives: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "message_id": item.get("message_id"),
            "score": item.get("score"),
            "delta_seconds": item.get("delta_seconds"),
        }
        for item in alternatives[:3]
    ]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


SIMPLE_REPORT_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neo4j Threads</title>
<style>
:root {
  --ink:#142033;
  --muted:#5f6f82;
  --line:#d5dce6;
  --bg:#eef3f8;
  --panel:#ffffff;
  --accent:#1f6feb;
  --accent-soft:#dbeafe;
  --hero:#102a43;
  --hero-2:#0f4c5c;
  --warn:#a15c07;
  --bad:#b42318;
  --ok:#157f5d;
  --shadow:0 20px 44px rgba(16, 42, 67, 0.08);
}
* { box-sizing:border-box; }
body {
  margin:0;
  font-family:"Trebuchet MS", "Segoe UI", sans-serif;
  background:radial-gradient(circle at top left, #ffffff 0, #eef3f8 38%, #e7eef6 100%);
  color:var(--ink);
}
header {
  padding:22px 24px 24px;
  background:linear-gradient(135deg, var(--hero) 0%, var(--hero-2) 100%);
  color:white;
  border-bottom:1px solid rgba(255,255,255,0.12);
}
h1 { margin:0 0 8px; font-size:28px; letter-spacing:0.01em; }
h2 { margin:0 0 10px; font-size:18px; }
h3 { margin:0; font-size:15px; }
p { margin:4px 0; color:var(--muted); }
header p { color:rgba(255,255,255,0.82); max-width:900px; }
button, input, select { font:inherit; }
main { display:grid; grid-template-columns:430px minmax(0, 1fr); gap:18px; padding:18px 24px 28px; }
.coverage, .metrics, .filters, .list, .detail, .result-summary {
  background:var(--panel);
  border:1px solid var(--line);
  border-radius:18px;
  box-shadow:var(--shadow);
}
.coverage {
  margin:18px 24px 0;
  padding:18px 18px 16px;
  position:relative;
  overflow:hidden;
}
.coverage::after {
  content:"";
  position:absolute;
  top:-30px;
  right:-30px;
  width:140px;
  height:140px;
  background:radial-gradient(circle, rgba(31,111,235,0.14), rgba(31,111,235,0));
  pointer-events:none;
}
.coverage strong { color:var(--ink); }
.metrics {
  margin:12px 24px 0;
  padding:12px;
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));
  gap:10px;
}
.metric {
  border:1px solid var(--line);
  border-radius:14px;
  padding:10px 12px;
  background:linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}
.metric span { display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:0.04em; }
.metric strong { display:block; font-size:22px; margin-top:4px; }
.filters { padding:14px; margin-bottom:12px; display:grid; gap:12px; }
.filter-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; }
label { display:grid; gap:5px; color:var(--muted); font-size:12px; }
label.span-2 { grid-column:1 / -1; }
input, select {
  width:100%;
  border:1px solid var(--line);
  border-radius:12px;
  padding:10px 11px;
  background:white;
  color:var(--ink);
}
.filter-actions { display:flex; justify-content:flex-end; }
.filter-actions button {
  border:1px solid #c1cbd8;
  border-radius:999px;
  background:#f8fafc;
  color:var(--ink);
  padding:8px 12px;
  cursor:pointer;
}
.result-summary { padding:12px 14px; margin-bottom:12px; }
.result-summary strong { color:var(--ink); }
.list { max-height:calc(100vh - 290px); overflow:auto; padding:8px; }
.thread-row {
  width:100%;
  border:1px solid transparent;
  border-radius:16px;
  background:linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  text-align:left;
  padding:14px 14px 14px 18px;
  cursor:pointer;
  margin-bottom:10px;
  position:relative;
}
.thread-row::before {
  content:"";
  position:absolute;
  left:0;
  top:8px;
  bottom:8px;
  width:6px;
  border-radius:999px;
  background:var(--channel-accent, var(--accent));
}
.thread-row:hover {
  border-color:#c8d7ea;
  transform:translateY(-1px);
}
.thread-row.active {
  border-color:#9cc0ff;
  background:linear-gradient(180deg, #edf4ff 0%, #f8fbff 100%);
  box-shadow:0 12px 24px rgba(31, 111, 235, 0.12);
}
.thread-headline,
.thread-tags,
.thread-meta,
.thread-submeta { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.thread-id { font-size:11px; color:var(--muted); letter-spacing:0.06em; text-transform:uppercase; }
.thread-title { display:block; color:var(--ink); font-weight:700; line-height:1.28; margin:8px 0 6px; }
.thread-meta, .thread-submeta { color:var(--muted); font-size:12px; }
.detail {
  min-height:620px;
  padding:16px;
  display:grid;
  gap:14px;
  align-content:start;
}
.detail-hero {
  border:1px solid var(--line);
  border-radius:18px;
  padding:16px 18px;
  background:linear-gradient(135deg, rgba(16, 42, 67, 0.03), rgba(15, 76, 92, 0.08));
  box-shadow:inset 0 0 0 1px rgba(255,255,255,0.35);
  position:relative;
}
.detail-hero::before {
  content:"";
  position:absolute;
  left:0;
  top:0;
  bottom:0;
  width:8px;
  border-radius:18px 0 0 18px;
  background:var(--thread-accent, var(--accent));
}
.detail-head { display:flex; justify-content:space-between; gap:16px; }
.detail-title { padding-left:10px; }
.detail-side { min-width:210px; display:grid; gap:10px; align-content:start; }
.detail-kpis {
  display:grid;
  grid-template-columns:repeat(2, minmax(0, 1fr));
  gap:8px;
}
.detail-kpi {
  border:1px solid var(--line);
  border-radius:12px;
  padding:8px 10px;
  background:rgba(255,255,255,0.75);
}
.detail-kpi span { display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:0.04em; }
.detail-kpi strong { display:block; margin-top:3px; font-size:16px; }
.thread-channel-strip { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; padding-left:10px; }
.badge {
  display:inline-flex;
  align-items:center;
  gap:6px;
  border:1px solid var(--line);
  border-radius:999px;
  padding:4px 10px;
  font-size:12px;
  margin:2px 4px 2px 0;
  background:#f4f6f8;
  color:var(--ink);
}
.badge.ok { color:var(--ok); border-color:#a9d7c0; background:#eef8f3; }
.badge.ambiguous, .badge.needs_review { color:var(--warn); border-color:#e2bd7c; background:#fff8e8; }
.badge.uncertain { color:var(--bad); border-color:#e4b4b4; background:#fff0f0; }
.channel-badge {
  border-color:color-mix(in srgb, var(--badge-accent, var(--accent)) 25%, white);
  background:color-mix(in srgb, var(--badge-accent, var(--accent)) 14%, white);
  color:var(--ink);
}
.message {
  border:1px solid var(--line);
  border-left:6px solid var(--thread-accent, #ccd6df);
  border-radius:16px;
  background:white;
  padding:12px 14px 12px 14px;
  margin:0;
  box-shadow:0 6px 18px rgba(20, 32, 51, 0.04);
}
.message-meta { color:var(--muted); font-size:12px; margin-bottom:8px; display:flex; flex-wrap:wrap; gap:8px; }
.message-content { white-space:pre-wrap; line-height:1.5; }
.message-stack { display:grid; gap:10px; }
.link-line { color:#335d7e; font-size:12px; margin-top:8px; }
details { margin-top:8px; }
summary { cursor:pointer; color:var(--accent); font-size:12px; }
pre { white-space:pre-wrap; overflow:auto; padding:10px; border-radius:10px; background:#f3f6f9; border:1px solid #e1e7ef; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
.empty { color:var(--muted); padding:18px; }
@media (max-width: 980px) {
  main { grid-template-columns:1fr; padding:12px; }
  .coverage, .metrics { margin-left:12px; margin-right:12px; }
  .list { max-height:420px; }
  .detail-head { display:block; }
  .detail-side { min-width:0; margin-top:12px; }
}
</style>
</head>
<body>
<header>
<h1>Neo4j Threads</h1>
<p>Interface de revisao com foco em navegao por canal, leitura de threads reconstruidas e inspeo visual das relaes inferidas.</p>
</header>
<section class="coverage" id="coverage"></section>
<section class="metrics" id="metrics"></section>
<main>
<aside>
<section class="filters">
  <div class="filter-grid">
    <label class="span-2">Buscar texto, usuario, keyword, thread_id ou canal
      <input id="query" type="search" placeholder="aura, cypher, USER_001, T_0001">
    </label>
    <label>Filtrar por canal
      <select id="channel"></select>
    </label>
    <label>Status
      <select id="status">
        <option value="">todos</option>
        <option value="ok">ok</option>
        <option value="ambiguous">ambiguous</option>
        <option value="needs_review">needs_review</option>
      </select>
    </label>
    <label>Tamanho minimo
      <input id="minSize" type="number" min="1" step="1" value="2">
    </label>
    <label>Ordenar
      <select id="sort">
        <option value="size">maiores primeiro</option>
        <option value="time">ordem temporal</option>
        <option value="confidence">maior confianca</option>
        <option value="review">revisao primeiro</option>
      </select>
    </label>
  </div>
  <div class="filter-actions">
    <button id="clearFilters" type="button">limpar filtros</button>
  </div>
</section>
<section class="result-summary" id="resultSummary"></section>
<section class="list" id="threadList"></section>
</aside>
<section class="detail" id="detail"></section>
</main>
<script>
const data = __REPORT_DATA__;
let filtered = [];
let selectedId = null;

const fmt = new Intl.NumberFormat('pt-BR');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}

function channelColor(channel) {
  let hash = 0;
  for (const ch of String(channel || 'unknown')) {
    hash = ((hash << 5) - hash) + ch.charCodeAt(0);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 62% 46%)`;
}

function badgeChannel(channel) {
  const accent = channelColor(channel);
  return `<span class="badge channel-badge" style="--badge-accent:${accent}">${escapeHtml(channel)}</span>`;
}

function renderCoverage() {
  const channels = Object.entries(data.coverage.channel_counts)
    .slice(0, 12)
    .map(([k, v]) => `${escapeHtml(k)}=${fmt.format(v)}`)
    .join(', ');
  const guilds = Object.entries(data.coverage.guild_counts).map(([k, v]) => `${escapeHtml(k)}=${fmt.format(v)}`).join(', ');
  document.getElementById('coverage').innerHTML = `
    <h2>Cobertura dos dados</h2>
    <p><strong>${fmt.format(data.coverage.message_count)}</strong> mensagens no arquivo de entrada para este escopo.</p>
    <p>Periodo: ${escapeHtml(data.coverage.first_message_at)} ate ${escapeHtml(data.coverage.last_message_at)}</p>
    <p>Servidor: ${guilds}</p>
    <p>Canais com mais volume: ${channels}</p>
    <p>${escapeHtml(data.coverage.note)}</p>
  `;
}

function renderMetrics() {
  const m = data.metrics;
  const rows = [
    ['threads', data.coverage.thread_count],
    ['singletons', m.single_message_threads],
    ['media msgs/thread', m.avg_messages_per_thread.toFixed(2)],
    ['mediana msgs/thread', m.median_messages_per_thread.toFixed(1)],
    ['ok', m.ok_threads],
    ['revisao', m.ambiguous_threads + m.needs_review_threads],
    ['edges explicitas', m.explicit_edges],
    ['edges inferidas', m.inferred_edges + m.uncertain_edges],
  ];
  document.getElementById('metrics').innerHTML = rows.map(([label, value]) => `
    <div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
  `).join('');
}

function initChannelOptions() {
  const select = document.getElementById('channel');
  const options = ['<option value="">todos os canais</option>'];
  for (const [channel, count] of Object.entries(data.coverage.channel_counts)) {
    options.push(`<option value="${escapeHtml(channel)}">${escapeHtml(channel)} (${fmt.format(count)})</option>`);
  }
  select.innerHTML = options.join('');
}

function renderResultSummary() {
  const selectedChannel = document.getElementById('channel').value;
  const totalMessages = filtered.reduce((sum, thread) => sum + thread.message_count, 0);
  const singletons = filtered.filter(thread => thread.message_count === 1).length;
  document.getElementById('resultSummary').innerHTML = `
    <h2>Resultado atual</h2>
    <p><strong>${fmt.format(filtered.length)}</strong> threads visiveis, <strong>${fmt.format(totalMessages)}</strong> mensagens agregadas e <strong>${fmt.format(singletons)}</strong> singletons neste recorte.</p>
    <p>Canal ativo: <strong>${escapeHtml(selectedChannel || 'todos os canais')}</strong></p>
  `;
}

function applyFilters() {
  const q = document.getElementById('query').value.trim().toLowerCase();
  const minSize = Number(document.getElementById('minSize').value || 1);
  const status = document.getElementById('status').value;
  const channel = document.getElementById('channel').value;
  const sort = document.getElementById('sort').value;
  filtered = data.threads.filter(thread => {
    const haystack = [
      thread.thread_id,
      thread.title,
      thread.status,
      thread.primary_channel,
      thread.channel_names.join(' '),
      thread.keywords.join(' '),
      thread.participants.join(' '),
      thread.messages.map(m => `${m.channel} ${m.content}`).join(' '),
    ].join(' ').toLowerCase();
    return thread.message_count >= minSize
      && (!status || thread.status === status)
      && (!channel || thread.channel_names.includes(channel))
      && (!q || haystack.includes(q));
  });
  filtered.sort((a, b) => {
    if (sort === 'time') return a.start_time.localeCompare(b.start_time);
    if (sort === 'confidence') return b.avg_confidence - a.avg_confidence;
    if (sort === 'review') return Number(b.status !== 'ok') - Number(a.status !== 'ok') || b.message_count - a.message_count;
    return b.message_count - a.message_count || a.start_time.localeCompare(b.start_time);
  });
  if (!filtered.some(thread => thread.thread_id === selectedId)) {
    selectedId = filtered[0]?.thread_id ?? null;
  }
  renderResultSummary();
  renderList();
  renderDetail();
}

function renderList() {
  const list = document.getElementById('threadList');
  if (!filtered.length) {
    list.innerHTML = '<div class="empty">Nenhuma thread para estes filtros.</div>';
    return;
  }
  list.innerHTML = filtered.map(thread => {
    const accent = channelColor(thread.primary_channel);
    const channels = thread.channel_names.slice(0, 2).map(channel => badgeChannel(channel)).join('');
    const moreChannels = thread.channel_names.length > 2 ? `<span class="badge">+${thread.channel_names.length - 2} canais</span>` : '';
    const statusBadge = `<span class="badge ${escapeHtml(thread.status)}">${escapeHtml(thread.status)}</span>`;
    const shapeBadge = `<span class="badge">${escapeHtml(thread.conversation_shape)}</span>`;
    const multiBadge = thread.multi_channel ? '<span class="badge">multi-canal</span>' : '';
    const participantPreview = escapeHtml(thread.participants.slice(0, 4).join(', ') || 'n/a');
    const keywordPreview = escapeHtml(thread.keywords.slice(0, 4).join(', ') || 'n/a');
    return `
      <button class="thread-row ${thread.thread_id === selectedId ? 'active' : ''}" data-thread="${escapeHtml(thread.thread_id)}" style="--channel-accent:${accent}">
        <div class="thread-headline">
          <span class="thread-id">${escapeHtml(thread.thread_id)}</span>
          ${channels}${moreChannels}
        </div>
        <span class="thread-title">${escapeHtml(thread.title)}</span>
        <div class="thread-tags">${statusBadge}${shapeBadge}${multiBadge}</div>
        <div class="thread-meta">
          <span>${thread.message_count} msgs</span>
          <span>${thread.participant_count} usuarios</span>
          <span>conf. ${thread.avg_confidence.toFixed(2)}</span>
          <span>${escapeHtml(thread.start_time.slice(0, 10))}</span>
        </div>
        <div class="thread-submeta">
          <span>participantes: ${participantPreview}</span>
          <span>keywords: ${keywordPreview}</span>
        </div>
      </button>
    `;
  }).join('');
  list.querySelectorAll('.thread-row').forEach(button => {
    button.addEventListener('click', () => {
      selectedId = button.dataset.thread;
      renderList();
      renderDetail();
    });
  });
}

function renderDetail() {
  const detail = document.getElementById('detail');
  const thread = data.threads.find(item => item.thread_id === selectedId);
  if (!thread) {
    detail.innerHTML = '<div class="empty">Selecione uma thread.</div>';
    return;
  }
  const accent = channelColor(thread.primary_channel);
  const badges = [
    `<span class="badge ${escapeHtml(thread.status)}">${escapeHtml(thread.status)}</span>`,
    `<span class="badge">${escapeHtml(thread.conversation_shape)}</span>`,
    `<span class="badge">explicit ${thread.explicit_edge_count}</span>`,
    `<span class="badge">inferred ${thread.inferred_edge_count}</span>`,
    `<span class="badge uncertain">uncertain ${thread.uncertain_edge_count}</span>`,
  ].join('');
  const channelBadges = thread.channel_names.map(channel => badgeChannel(channel)).join('');
  const messages = thread.messages.map(message => {
    const messageAccent = channelColor(message.channel || thread.primary_channel);
    const link = message.parent_message_id ? `
      <div class="link-line">responde/continua ${escapeHtml(message.parent_message_id)}
      · score ${escapeHtml(message.parent_score)}
      · ${escapeHtml(message.link_type || '')}
      · ${escapeHtml((message.evidence.evidence_labels || []).join(', ') || 'sem labels')}</div>
    ` : '';
    const evidence = Object.keys(message.evidence || {}).length ? `
      <details><summary>evidencia</summary><pre>${escapeHtml(JSON.stringify(message.evidence, null, 2))}</pre></details>
    ` : '';
    const alternatives = message.alternatives?.length ? `
      <details><summary>candidatos alternativos</summary><pre>${escapeHtml(JSON.stringify(message.alternatives, null, 2))}</pre></details>
    ` : '';
    return `
      <article class="message" style="--thread-accent:${messageAccent}">
        <div class="message-meta">
          <span>#${message.position}</span>
          <span>${escapeHtml(message.author)}</span>
          <span>${badgeChannel(message.channel)}</span>
          <span>${escapeHtml(message.timestamp)}</span>
          <span>${escapeHtml(message.message_id)}</span>
        </div>
        <div class="message-content">${escapeHtml(message.content)}</div>
        ${link}${evidence}${alternatives}
      </article>
    `;
  }).join('');
  detail.innerHTML = `
    <section class="detail-hero" style="--thread-accent:${accent}">
      <div class="detail-head">
        <div class="detail-title">
          <h2>${escapeHtml(thread.thread_id)} · ${escapeHtml(thread.title)}</h2>
          <p>${thread.message_count} mensagens · ${thread.participant_count} usuarios · conf. ${thread.avg_confidence.toFixed(2)}</p>
          <p>${escapeHtml(thread.start_time)} ate ${escapeHtml(thread.end_time)}</p>
          <p>keywords: ${escapeHtml(thread.keywords.join(', ') || 'n/a')}</p>
          <p>revisao: ${escapeHtml(thread.needs_review_reasons.join(', ') || 'none')}</p>
          <div>${badges}</div>
          <div class="thread-channel-strip">${channelBadges}</div>
        </div>
        <div class="detail-side">
          <div class="detail-kpis">
            <div class="detail-kpi"><span>Canal dominante</span><strong>${escapeHtml(thread.primary_channel)}</strong></div>
            <div class="detail-kpi"><span>Canais</span><strong>${thread.channel_names.length}</strong></div>
            <div class="detail-kpi"><span>Root</span><strong>${escapeHtml(thread.root_message_id)}</strong></div>
            <div class="detail-kpi"><span>Duracao</span><strong>${fmt.format(Math.round(thread.duration_seconds))}s</strong></div>
          </div>
          <div><a href="${escapeHtml(thread.detail_url)}">abrir pagina simples da thread</a></div>
        </div>
      </div>
    </section>
    <section class="message-stack">${messages}</section>
  `;
}

function resetFilters() {
  document.getElementById('query').value = '';
  document.getElementById('channel').value = '';
  document.getElementById('status').value = '';
  document.getElementById('minSize').value = '2';
  document.getElementById('sort').value = 'size';
  applyFilters();
}

['query', 'minSize', 'status', 'sort', 'channel'].forEach(id => document.getElementById(id).addEventListener('input', applyFilters));
document.getElementById('clearFilters').addEventListener('click', resetFilters);
renderCoverage();
renderMetrics();
initChannelOptions();
applyFilters();
</script>
</body>
</html>
"""


THREAD_DETAIL_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thread detail</title>
<style>
body { margin:0; font-family:"Trebuchet MS", "Segoe UI", sans-serif; background:#eef3f8; color:#172026; }
main { max-width:1080px; margin:0 auto; padding:22px; }
section { background:white; border:1px solid #d9e0e6; border-radius:16px; padding:16px; margin-bottom:14px; box-shadow:0 12px 32px rgba(20, 32, 51, 0.06); }
h1 { margin:0 0 8px; font-size:24px; }
h2 { margin:0 0 10px; font-size:18px; }
p { color:#5f6b76; margin:4px 0; }
.hero { position:relative; overflow:hidden; }
.hero::before { content:""; position:absolute; left:0; top:0; bottom:0; width:8px; background:var(--thread-accent, #2364aa); }
.hero-inner { padding-left:12px; }
.badge { display:inline-flex; align-items:center; gap:6px; border:1px solid #d9e0e6; border-radius:999px; padding:4px 10px; font-size:12px; background:#f4f6f8; margin:2px 6px 2px 0; }
.message { border:1px solid #d9e0e6; border-left:6px solid var(--message-accent, #ccd6df); border-radius:14px; padding:12px 14px; margin-bottom:10px; background:#fff; }
.meta { color:#5f6b76; font-size:12px; margin-bottom:7px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.content { white-space:pre-wrap; line-height:1.5; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { border-bottom:1px solid #d9e0e6; text-align:left; padding:8px; vertical-align:top; }
pre { white-space:pre-wrap; overflow:auto; background:#f1f4f7; padding:8px; border-radius:8px; }
</style>
</head>
<body>
<main id="app"></main>
<script>
const data = __THREAD_DATA__;
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function channelColor(channel) {
  let hash = 0;
  for (const ch of String(channel || 'unknown')) {
    hash = ((hash << 5) - hash) + ch.charCodeAt(0);
    hash |= 0;
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 62% 46%)`;
}
function channelBadge(channel) {
  return `<span class="badge">${escapeHtml(channel)}</span>`;
}
const messages = data.messages.map(message => `
  <article class="message" style="--message-accent:${channelColor(message.channel)}">
    <div class="meta">#${message.position} · ${escapeHtml(message.author)} · ${channelBadge(message.channel)} · ${escapeHtml(message.timestamp)} · ${escapeHtml(message.message_id)}</div>
    <div class="content">${escapeHtml(message.content)}</div>
  </article>
`).join('');
const links = data.links.length ? data.links.map(link => `
  <tr>
    <td>${escapeHtml(link.source)}</td>
    <td>${escapeHtml(link.target)}</td>
    <td>${escapeHtml(link.type)}</td>
    <td>${Number(link.confidence).toFixed(2)}</td>
    <td><pre>${escapeHtml(JSON.stringify(link.evidence, null, 2))}</pre></td>
  </tr>
`).join('') : '<tr><td colspan="5">Sem links internos.</td></tr>';
document.getElementById('app').innerHTML = `
  <section class="hero" style="--thread-accent:${channelColor(data.thread.primary_channel)}">
    <div class="hero-inner">
      <h1>${escapeHtml(data.thread.thread_id)} · ${escapeHtml(data.thread.title)}</h1>
      <p>${data.thread.message_count} mensagens · ${data.thread.participant_count} usuarios · conf. ${Number(data.thread.avg_confidence).toFixed(2)}</p>
      <p>${escapeHtml(data.thread.start_time)} ate ${escapeHtml(data.thread.end_time)}</p>
      <p>Status: ${escapeHtml(data.thread.status)} · Revisao: ${escapeHtml((data.thread.needs_review_reasons || []).join(', ') || 'none')}</p>
      <p>Canal dominante: ${escapeHtml(data.thread.primary_channel)}</p>
      <div>${(data.thread.channel_names || []).map(channelBadge).join('')}</div>
    </div>
  </section>
  <section>
    <h2>Mensagens</h2>
    ${messages}
  </section>
  <section>
    <h2>Links</h2>
    <table>
      <thead><tr><th>source</th><th>target</th><th>tipo</th><th>conf.</th><th>evidencia</th></tr></thead>
      <tbody>${links}</tbody>
    </table>
  </section>
`;
</script>
</body>
</html>
"""
