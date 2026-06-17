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
    message_by_id = {message.message_id: message for message in messages}
    edges_by_source = {edge.source_message_id: edge for edge in graph_edges}
    candidate_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_pairs:
        candidate_by_source[row["source_message_id"]].append(row)
    for rows in candidate_by_source.values():
        rows.sort(key=lambda row: int(row.get("candidate_rank") or 999))

    cards = []
    for thread in threads:
        rows = [row for row in thread_messages if row["thread_id"] == thread.thread_id]
        message_html = []
        for row in rows:
            edge = edges_by_source.get(row["message_id"])
            evidence = {}
            alternatives = []
            if edge:
                evidence = edge.evidence
                alternatives = edge.alternative_parents
            labels = evidence.get("evidence_labels") if isinstance(evidence, dict) else None
            labels_text = ", ".join(labels or [])
            parent_line = ""
            if row["parent_message_id"]:
                parent_line = (
                    "<div class='parent-line'>↳ responde/continua "
                    f"<code>{html_escape(row['parent_message_id'])}</code> | "
                    f"score={html_escape(row['parent_score'])} | "
                    f"tipo={html_escape(row['link_type'])} | evidencias: {html_escape(labels_text or 'n/a')}</div>"
                )
            alt_line = ""
            if alternatives:
                alt_line = (
                    "<details><summary>candidatos alternativos</summary><pre>"
                    + html_escape(json.dumps(alternatives, ensure_ascii=False, indent=2))
                    + "</pre></details>"
                )
            evidence_line = ""
            if evidence:
                evidence_line = (
                    "<details><summary>evidencia do link</summary><pre>"
                    + html_escape(json.dumps(evidence, ensure_ascii=False, indent=2))
                    + "</pre></details>"
                )
            message_html.append(
                "<article class='message'>"
                f"<div class='message-meta'><strong>{html_escape(row['author_id'])}</strong> · "
                f"{html_escape(row['timestamp'])} · <code>{html_escape(row['message_id'])}</code></div>"
                f"<div class='message-body'>{html_escape(row['content_normalized'])}</div>"
                f"{parent_line}{evidence_line}{alt_line}"
                "</article>"
            )

        badges = [
            f"<span class='badge'>{html_escape(thread.conversation_shape)}</span>",
            f"<span class='badge status-{html_escape(thread.status)}'>{html_escape(thread.status)}</span>",
        ]
        if thread.explicit_edge_count:
            badges.append(f"<span class='badge explicit'>explicit {thread.explicit_edge_count}</span>")
        if thread.inferred_edge_count:
            badges.append(f"<span class='badge inferred'>inferred {thread.inferred_edge_count}</span>")
        if thread.uncertain_edge_count:
            badges.append(f"<span class='badge uncertain'>uncertain {thread.uncertain_edge_count}</span>")
        if thread.needs_review_reasons:
            badges.append("<span class='badge review'>review</span>")

        graph_link = f"thread_graphs/{thread.thread_id}.html"
        cards.append(
            "<section class='thread-card' "
            f"data-confidence='{thread.avg_confidence}' "
            f"data-size='{thread.message_count}' "
            f"data-participants='{html_escape(' '.join(thread.participants))}' "
            f"data-keywords='{html_escape(' '.join(thread.keywords))}' "
            f"data-status='{html_escape(thread.status)}'>"
            "<header class='thread-header'>"
            "<div>"
            f"<h2>{html_escape(thread.thread_id)} · {html_escape(thread.title)}</h2>"
            f"<p>{html_escape(thread.start_time.isoformat())} ate {html_escape(thread.end_time.isoformat())} · "
            f"{thread.message_count} mensagens · {thread.participant_count} participantes · "
            f"conf. media {thread.avg_confidence:.2f}</p>"
            f"<p>root <code>{html_escape(thread.root_message_id)}</code> · participantes "
            f"{html_escape(', '.join(thread.participants))}</p>"
            f"<p>keywords: {html_escape(', '.join(thread.keywords) or 'n/a')}</p>"
            f"<p>future fields: neutral_summary={html_escape(thread.neutral_summary)}; "
            "scd_summary=not computed yet; incivility_label=not computed yet; "
            "derailment_risk=not computed yet; derailment_point=not computed yet; "
            "tone_markers=not computed yet; tension_triggers=not computed yet</p>"
            f"<p>review: {html_escape(', '.join(thread.needs_review_reasons) or 'none')}</p>"
            "</div>"
            f"<a class='graph-link' href='{html_escape(graph_link)}'>abrir grafo</a>"
            "</header>"
            f"<div class='badges'>{''.join(badges)}</div>"
            "<div class='messages'>"
            + "".join(message_html)
            + "</div>"
            "</section>"
        )

    overview = _overview_html(threads, graph_edges, thread_messages)
    review = _review_html(threads, messages, graph_edges, candidate_by_source)
    html = HTML_TEMPLATE.replace("__OVERVIEW__", overview)
    html = html.replace("__THREAD_CARDS__", "\n".join(cards))
    html = html.replace("__REVIEW__", review)
    output_path.write_text(html, encoding="utf-8")


def generate_thread_graph_reports(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    output_dir: Path,
) -> None:
    message_by_id = {message.message_id: message for message in messages}
    edges_by_thread: dict[str, list[EdgeRecord]] = defaultdict(list)
    thread_by_message: dict[str, str] = {}
    for thread in threads:
        for message_id in thread.message_ids:
            thread_by_message[message_id] = thread.thread_id
    for edge in graph_edges:
        if thread_by_message.get(edge.source_message_id) == thread_by_message.get(edge.target_message_id):
            edges_by_thread[thread_by_message[edge.source_message_id]].append(edge)

    for thread in threads:
        nodes = []
        for index, message_id in enumerate(thread.message_ids):
            message = message_by_id[message_id]
            nodes.append(
                {
                    "id": message.message_id,
                    "label": f"{index + 1}. {message.author_anon}",
                    "author": message.author_anon,
                    "timestamp": message.timestamp_iso,
                    "content": message.content_normalized,
                    "x": index,
                    "lane": thread.participants.index(message.author_anon or "USER_UNKNOWN")
                    if (message.author_anon or "USER_UNKNOWN") in thread.participants
                    else 0,
                }
            )
        edges = [
            {
                "source": edge.source_message_id,
                "target": edge.target_message_id,
                "edge_type": edge.edge_type,
                "confidence": edge.confidence,
                "method": edge.method,
                "evidence": edge.evidence,
                "alternative_parents": edge.alternative_parents,
            }
            for edge in edges_by_thread[thread.thread_id]
        ]
        payload = {"thread": _thread_payload(thread), "nodes": nodes, "edges": edges}
        html = GRAPH_TEMPLATE.replace("__GRAPH_DATA__", json.dumps(payload, ensure_ascii=False))
        (output_dir / f"{thread.thread_id}.html").write_text(html, encoding="utf-8")


def generate_summary_markdown(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    merge_suggestions: list[dict[str, Any]],
    output_path: Path,
) -> None:
    sizes = [thread.message_count for thread in threads]
    explicit = sum(edge.edge_type in {"explicit_reply", "native_thread", "quoted_message_link"} for edge in graph_edges)
    inferred = sum(edge.edge_type == "inferred" for edge in graph_edges)
    uncertain = sum(edge.edge_type == "uncertain" for edge in graph_edges)
    total_edges = len(graph_edges) or 1
    status_counts = Counter(thread.status for thread in threads)
    lines = [
        "# Neo4J conversation disentanglement summary",
        "",
        f"- Messages: {len(messages)}",
        f"- Threads: {len(threads)}",
        f"- Avg messages/thread: {(sum(sizes) / len(sizes)) if sizes else 0:.2f}",
        f"- Median messages/thread: {_median(sizes):.2f}",
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
        for suggestion in merge_suggestions:
            lines.append(
                "- "
                f"{suggestion['left_thread_id']} + {suggestion['right_thread_id']} "
                f"gap={suggestion['gap_seconds']:.0f}s "
                f"keywords={', '.join(suggestion['shared_keywords'])}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Notes", ""])
    lines.append("- Incivility, SCD and derailment fields are placeholders only.")
    lines.append("- User identifiers are anonymized as USER_XXX in generated reports.")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _overview_html(
    threads: list[ThreadRecord],
    graph_edges: list[EdgeRecord],
    thread_messages: list[dict[str, Any]],
) -> str:
    sizes = [thread.message_count for thread in threads]
    explicit = sum(edge.edge_type in {"explicit_reply", "native_thread", "quoted_message_link"} for edge in graph_edges)
    inferred = sum(edge.edge_type == "inferred" for edge in graph_edges)
    uncertain = sum(edge.edge_type == "uncertain" for edge in graph_edges)
    total_edges = len(graph_edges) or 1
    ambiguous = sum(thread.status in {"ambiguous", "needs_review"} for thread in threads)
    metrics = [
        ("threads", len(threads)),
        ("media msgs/thread", f"{(sum(sizes) / len(sizes)) if sizes else 0:.2f}"),
        ("mediana msgs/thread", f"{_median(sizes):.2f}"),
        ("threads curtas", sum(size <= 2 for size in sizes)),
        ("threads longas", sum(size >= 15 for size in sizes)),
        ("ambiguas", ambiguous),
        ("% explicit", f"{explicit / total_edges:.1%}"),
        ("% inferred", f"{inferred / total_edges:.1%}"),
        ("% uncertain", f"{uncertain / total_edges:.1%}"),
        ("conf. geral", f"{_avg([thread.avg_confidence for thread in threads]):.3f}"),
    ]
    bars = "".join(
        f"<div class='bar' style='height:{max(8, min(120, size * 8))}px' title='{size} mensagens'></div>"
        for size in sizes[:200]
    )
    confidence_bars = "".join(
        f"<div class='bar confidence' style='height:{max(8, min(120, thread.avg_confidence * 120))}px' "
        f"title='{thread.thread_id}: {thread.avg_confidence:.2f}'></div>"
        for thread in threads[:200]
    )
    message_ticks = "".join(
        "<span class='tick' "
        f"title='{html_escape(row['timestamp'])} · {html_escape(row['thread_id'])} · {html_escape(row['message_id'])}' "
        f"data-thread='{html_escape(row['thread_id'])}'></span>"
        for row in thread_messages[:1000]
    )
    return (
        "<section class='overview'>"
        + "".join(f"<div class='metric'><span>{html_escape(label)}</span><strong>{html_escape(value)}</strong></div>" for label, value in metrics)
        + "</section>"
        "<section class='timeline'><h2>Timeline do canal</h2>"
        "<p>Cada marca representa uma mensagem em ordem temporal, associada ao seu thread_id.</p>"
        f"<div class='ticks'>{message_ticks}</div>"
        "<p>Cada barra resume o tamanho de uma thread em ordem temporal.</p>"
        f"<div class='bars'>{bars}</div>"
        "<h2>Distribuicao de confianca</h2>"
        f"<div class='bars'>{confidence_bars}</div>"
        "</section>"
    )


def _review_html(
    threads: list[ThreadRecord],
    messages: list[MessageRecord],
    graph_edges: list[EdgeRecord],
    candidate_by_source: dict[str, list[dict[str, Any]]],
) -> str:
    message_by_id = {message.message_id: message for message in messages}
    items = []
    for thread in threads:
        for reason in thread.needs_review_reasons:
            items.append(
                f"<li><strong>{html_escape(thread.thread_id)}</strong>: {html_escape(reason)} "
                f"({thread.message_count} mensagens, conf. {thread.avg_confidence:.2f})</li>"
            )
    for message in messages:
        rows = candidate_by_source.get(message.message_id, [])
        if len(rows) >= 2 and float(rows[0]["score"]) - float(rows[1]["score"]) <= 0.08:
            items.append(
                f"<li><strong>{html_escape(message.message_id)}</strong>: multiple_close_parents "
                f"({html_escape(rows[0]['target_message_id'])}={rows[0]['score']}, "
                f"{html_escape(rows[1]['target_message_id'])}={rows[1]['score']})</li>"
            )
    for edge in graph_edges:
        if edge.edge_type in {"inferred", "uncertain"} and edge.evidence.get("delta_seconds", 0) > 21600:
            source = message_by_id.get(edge.source_message_id)
            target = message_by_id.get(edge.target_message_id)
            items.append(
                "<li><strong>"
                f"{html_escape(edge.source_message_id)}</strong>: large_temporal_gap "
                f"para {html_escape(edge.target_message_id)} "
                f"({html_escape(source.timestamp_iso if source else '')} -> "
                f"{html_escape(target.timestamp_iso if target else '')})</li>"
            )
    if not items:
        items.append("<li>none</li>")
    return "<section class='review'><h2>Ambiguity and Review View</h2><ul>" + "\n".join(items) + "</ul></section>"


def _thread_payload(thread: ThreadRecord) -> dict[str, Any]:
    return {
        "thread_id": thread.thread_id,
        "title": thread.title,
        "root_message_id": thread.root_message_id,
        "start_time": thread.start_time.isoformat(),
        "end_time": thread.end_time.isoformat(),
        "message_count": thread.message_count,
        "participant_count": thread.participant_count,
        "participants": thread.participants,
        "avg_confidence": thread.avg_confidence,
        "status": thread.status,
        "needs_review_reasons": thread.needs_review_reasons,
    }


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


HTML_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Neo4J Thread Explorer</title>
<style>
:root { color-scheme: light; --ink:#172026; --muted:#5a6872; --line:#d8dee4; --surface:#ffffff; --soft:#f3f6f8; --accent:#0d6efd; --ok:#1f7a4d; --warn:#b35c00; --bad:#a13434; }
* { box-sizing: border-box; }
body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; color:var(--ink); background:#f7f9fb; }
header.top { padding:24px 32px 12px; background:#fff; border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; }
h1 { margin:0 0 8px; font-size:28px; letter-spacing:0; }
h2 { margin:0 0 8px; font-size:18px; letter-spacing:0; }
p { margin:4px 0; color:var(--muted); }
main { padding:24px 32px 48px; max-width:1400px; margin:0 auto; }
.controls { display:grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap:12px; margin-top:16px; }
.controls label { display:flex; flex-direction:column; gap:6px; font-size:12px; color:var(--muted); }
input, select { padding:8px 10px; border:1px solid var(--line); border-radius:6px; background:#fff; color:var(--ink); }
.overview { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:12px; margin-bottom:20px; }
.metric { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:12px; }
.metric span { display:block; color:var(--muted); font-size:12px; }
.metric strong { display:block; font-size:22px; margin-top:4px; }
.timeline, .review { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:16px; margin:16px 0; }
.bars { display:flex; align-items:end; gap:3px; min-height:130px; overflow:auto; padding-top:8px; }
.bar { width:10px; min-width:10px; background:#4b8bbe; border-radius:3px 3px 0 0; }
.bar.confidence { background:#7a8f38; }
.ticks { display:flex; gap:2px; overflow:auto; padding:8px 0 12px; border-bottom:1px solid var(--line); margin-bottom:12px; }
.tick { display:block; width:8px; min-width:8px; height:28px; border-radius:3px; background:#6f7f8c; }
.tick:nth-child(3n) { background:#4b8bbe; }
.tick:nth-child(5n) { background:#7a8f38; }
.tick:nth-child(7n) { background:#b35c00; }
.thread-card { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:16px; margin:16px 0; }
.thread-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.graph-link { display:inline-flex; align-items:center; justify-content:center; border:1px solid var(--accent); color:#fff; background:var(--accent); text-decoration:none; border-radius:6px; padding:8px 10px; white-space:nowrap; }
.badges { display:flex; flex-wrap:wrap; gap:6px; margin:12px 0; }
.badge { border:1px solid var(--line); background:var(--soft); color:var(--ink); border-radius:999px; padding:3px 8px; font-size:12px; }
.badge.explicit { background:#e8f4ff; border-color:#9bc8ff; }
.badge.inferred { background:#ecf8f0; border-color:#9ad3ad; }
.badge.uncertain, .status-ambiguous, .status-needs_review { background:#fff4e5; border-color:#f2b36d; }
.badge.review { background:#ffecec; border-color:#df9999; }
.message { border-top:1px solid var(--line); padding:12px 0; }
.message-meta { color:var(--muted); font-size:13px; margin-bottom:6px; }
.message-body { white-space:pre-wrap; line-height:1.45; }
.parent-line { margin-top:6px; color:#37556b; font-size:13px; }
details { margin-top:6px; }
summary { cursor:pointer; color:var(--accent); font-size:13px; }
pre { white-space:pre-wrap; overflow:auto; background:#f0f3f5; padding:10px; border-radius:6px; }
code { background:#eef2f5; padding:1px 4px; border-radius:4px; }
.hidden { display:none; }
@media (max-width: 760px) {
  header.top, main { padding-left:16px; padding-right:16px; }
  .controls { grid-template-columns:1fr; }
  .thread-header { flex-direction:column; }
}
</style>
</head>
<body>
<header class="top">
<h1>Neo4J Thread Explorer</h1>
<p>Conversation disentanglement audit report. User identifiers are anonymized; incivility fields are not computed yet.</p>
<div class="controls">
<label>Texto, participante ou keyword<input id="q" type="search" placeholder="USER_001, cypher, T_0001"></label>
<label>Confianca minima<input id="minConfidence" type="number" min="0" max="1" step="0.05" value="0"></label>
<label>Tamanho minimo<input id="minSize" type="number" min="1" step="1" value="1"></label>
<label>Status<select id="status"><option value="">todos</option><option value="ok">ok</option><option value="ambiguous">ambiguous</option><option value="needs_review">needs_review</option></select></label>
</div>
</header>
<main>
__OVERVIEW__
__REVIEW__
<section id="threads">
__THREAD_CARDS__
</section>
</main>
<script>
const cards = [...document.querySelectorAll('.thread-card')];
const inputs = ['q', 'minConfidence', 'minSize', 'status'].map(id => document.getElementById(id));
function applyFilters() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const minConfidence = Number(document.getElementById('minConfidence').value || 0);
  const minSize = Number(document.getElementById('minSize').value || 1);
  const status = document.getElementById('status').value;
  cards.forEach(card => {
    const haystack = (card.innerText + ' ' + card.dataset.participants + ' ' + card.dataset.keywords).toLowerCase();
    const ok = (!q || haystack.includes(q))
      && Number(card.dataset.confidence) >= minConfidence
      && Number(card.dataset.size) >= minSize
      && (!status || card.dataset.status === status);
    card.classList.toggle('hidden', !ok);
  });
}
inputs.forEach(input => input.addEventListener('input', applyFilters));
</script>
</body>
</html>
"""


GRAPH_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thread graph</title>
<style>
body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; color:#172026; background:#f7f9fb; }
main { display:grid; grid-template-columns:minmax(0, 1fr) 360px; min-height:100vh; }
#canvas { background:#fff; border-right:1px solid #d8dee4; width:100%; height:100vh; }
aside { padding:18px; overflow:auto; }
h1 { font-size:20px; margin:0 0 8px; }
p { color:#5a6872; }
pre { white-space:pre-wrap; background:#eef2f5; padding:10px; border-radius:6px; overflow:auto; }
.node { cursor:pointer; }
.edge { cursor:pointer; }
@media (max-width: 880px) { main { grid-template-columns:1fr; } #canvas { height:70vh; border-right:0; border-bottom:1px solid #d8dee4; } }
</style>
</head>
<body>
<main>
<svg id="canvas" role="img" aria-label="Thread graph"></svg>
<aside>
<h1 id="title"></h1>
<p id="meta"></p>
<div id="detail">Clique em um no ou aresta para inspecionar.</div>
</aside>
</main>
<script>
const data = __GRAPH_DATA__;
const svg = document.getElementById('canvas');
const detail = document.getElementById('detail');
document.getElementById('title').textContent = data.thread.thread_id + ' · ' + data.thread.title;
document.getElementById('meta').textContent = `${data.thread.message_count} mensagens · conf. ${data.thread.avg_confidence}`;
const width = 1200;
const height = Math.max(520, 120 + data.thread.participants.length * 90);
svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
const nodeById = new Map(data.nodes.map((node, index) => {
  const x = 80 + (index * Math.max(90, (width - 160) / Math.max(1, data.nodes.length - 1)));
  const y = 80 + node.lane * 90;
  return [node.id, {...node, x, y}];
}));
function color(edgeType) {
  if (edgeType === 'explicit_reply' || edgeType === 'native_thread' || edgeType === 'quoted_message_link') return '#0d6efd';
  if (edgeType === 'uncertain') return '#b35c00';
  return '#1f7a4d';
}
function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
data.edges.forEach(edge => {
  const source = nodeById.get(edge.source);
  const target = nodeById.get(edge.target);
  if (!source || !target) return;
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', source.x);
  line.setAttribute('y1', source.y);
  line.setAttribute('x2', target.x);
  line.setAttribute('y2', target.y);
  line.setAttribute('stroke', color(edge.edge_type));
  line.setAttribute('stroke-width', String(1 + edge.confidence * 4));
  line.setAttribute('stroke-opacity', String(0.35 + edge.confidence * 0.65));
  line.classList.add('edge');
  line.addEventListener('click', () => {
    detail.innerHTML = `<h2>Aresta</h2><p><code>${escapeHtml(edge.source)}</code> responde/continua <code>${escapeHtml(edge.target)}</code></p><pre>${escapeHtml(JSON.stringify(edge, null, 2))}</pre>`;
  });
  svg.appendChild(line);
});
data.nodes.forEach(node => {
  const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  group.classList.add('node');
  group.setAttribute('transform', `translate(${node.x}, ${node.y})`);
  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('r', '22');
  circle.setAttribute('fill', '#ffffff');
  circle.setAttribute('stroke', '#172026');
  circle.setAttribute('stroke-width', '1.5');
  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('dy', '4');
  text.setAttribute('font-size', '11');
  text.textContent = node.label;
  group.appendChild(circle);
  group.appendChild(text);
  group.addEventListener('click', () => {
    detail.innerHTML = `<h2>${escapeHtml(node.id)}</h2><p>${escapeHtml(node.author)} · ${escapeHtml(node.timestamp)}</p><pre>${escapeHtml(node.content)}</pre>`;
  });
  svg.appendChild(group);
});
</script>
</body>
</html>
"""
