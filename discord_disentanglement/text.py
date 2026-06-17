from __future__ import annotations

import math
import re
from collections import Counter
from html import escape
from typing import Iterable
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
DISCORD_MESSAGE_URL_RE = re.compile(
    r"https?://(?:canary\.|ptb\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild>\d+|@me)/(?P<channel>\d+)/(?P<message>\d+)",
    re.IGNORECASE,
)
USER_MENTION_RE = re.compile(r"<@!?([A-Za-z0-9_]+)>")
CHANNEL_MENTION_RE = re.compile(r"<#(\d+)>")
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+", re.UNICODE)

STOPWORDS = {
    "a",
    "as",
    "and",
    "an",
    "are",
    "ao",
    "aos",
    "at",
    "be",
    "been",
    "by",
    "can",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "for",
    "from",
    "have",
    "has",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "just",
    "like",
    "na",
    "nas",
    "no",
    "nos",
    "not",
    "o",
    "of",
    "on",
    "os",
    "or",
    "our",
    "para",
    "por",
    "que",
    "that",
    "there",
    "them",
    "they",
    "the",
    "this",
    "to",
    "um",
    "uma",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
    "you",
    "your",
}

TECHNICAL_TERMS = {
    "api",
    "apoc",
    "async",
    "backend",
    "bug",
    "build",
    "cache",
    "class",
    "cli",
    "cluster",
    "code",
    "commit",
    "compile",
    "constraint",
    "cypher",
    "database",
    "debug",
    "dependency",
    "docker",
    "driver",
    "edge",
    "endpoint",
    "error",
    "exception",
    "frontend",
    "function",
    "graph",
    "graphql",
    "index",
    "java",
    "javascript",
    "json",
    "kubernetes",
    "linux",
    "merge",
    "method",
    "neo4j",
    "node",
    "npm",
    "package",
    "pip",
    "plugin",
    "python",
    "query",
    "relationship",
    "repo",
    "request",
    "response",
    "schema",
    "script",
    "server",
    "stack",
    "transaction",
    "traceback",
    "typescript",
    "version",
}

ERROR_MARKER_RE = re.compile(
    r"\b(error|exception|traceback|typeerror|valueerror|syntaxerror|stack trace|failed|failure)\b",
    re.IGNORECASE,
)
RESPONSE_START_RE = re.compile(
    r"^\s*(sim|nao|não|isso|depende|tenta|verifica|use|usa|voce|você|you|try|check|yes|no)\b",
    re.IGNORECASE,
)
DISAGREEMENT_RE = re.compile(
    r"\b(mas|porem|porém|na verdade|nao e isso|não é isso|however|actually|but)\b",
    re.IGNORECASE,
)
REASON_RE = re.compile(r"\b(porque|pois|entao|então|because|since|therefore)\b", re.IGNORECASE)
SECOND_PERSON_RE = re.compile(r"\b(voce|você|seu|sua|teu|tua|you|your)\b", re.IGNORECASE)


def coerce_text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def extract_url_hosts(text: str) -> list[str]:
    hosts: list[str] = []
    for match in URL_RE.finditer(text):
        try:
            host = urlparse(match.group(0)).netloc.lower()
        except ValueError:
            continue
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def normalize_content(
    content: str,
    author_alias_by_id: dict[str, str],
    channel_alias_by_id: dict[str, str],
    attachments: list[dict[str, object]] | None = None,
) -> tuple[str, list[str], list[str]]:
    mention_ids: list[str] = []
    channel_ids: list[str] = []

    def replace_user(match: re.Match[str]) -> str:
        user_id = match.group(1)
        mention_ids.append(user_id)
        return author_alias_by_id.setdefault(user_id, f"USER_{len(author_alias_by_id) + 1:03d}")

    def replace_channel(match: re.Match[str]) -> str:
        channel_id = match.group(1)
        channel_ids.append(channel_id)
        return channel_alias_by_id.setdefault(
            channel_id, f"CHANNEL_{len(channel_alias_by_id) + 1:03d}"
        )

    normalized = CODE_BLOCK_RE.sub("<CODE_BLOCK>", content)
    normalized = USER_MENTION_RE.sub(replace_user, normalized)
    normalized = CHANNEL_MENTION_RE.sub(replace_channel, normalized)
    normalized = URL_RE.sub("<URL>", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    attachment_markers: list[str] = []
    for attachment in attachments or []:
        content_type = str(attachment.get("content_type") or attachment.get("type") or "unknown")
        attachment_markers.append(f"<ATTACHMENT:{content_type.split(';')[0]}>")
    if attachment_markers:
        normalized = (normalized + " " + " ".join(attachment_markers)).strip()
    return normalized, mention_ids, channel_ids


def tokenize(text: str) -> list[str]:
    tokens = [token.lower().strip(".") for token in TOKEN_RE.findall(text)]
    return [token for token in tokens if token and token not in STOPWORDS and token != "url"]


def technical_tokens(tokens: Iterable[str]) -> list[str]:
    tech: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in TECHNICAL_TERMS or "." in lowered or lowered.startswith(("py", "js")):
            if lowered not in tech:
                tech.append(lowered)
    return tech


def lexical_overlap(source_tokens: list[str], target_tokens: list[str]) -> float:
    source_set = set(source_tokens)
    target_set = set(target_tokens)
    if not source_set or not target_set:
        return 0.0
    return len(source_set & target_set) / len(source_set | target_set)


def build_tfidf_vectors(tokenized_docs: list[list[str]]) -> list[dict[str, float]]:
    doc_count = len(tokenized_docs)
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_docs:
        document_frequency.update(set(tokens))

    vectors: list[dict[str, float]] = []
    for tokens in tokenized_docs:
        counts = Counter(tokens)
        length = sum(counts.values()) or 1
        vector: dict[str, float] = {}
        for token, count in counts.items():
            idf = math.log((1 + doc_count) / (1 + document_frequency[token])) + 1
            vector[token] = (count / length) * idf
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors.append({token: value / norm for token, value in vector.items()})
    return vectors


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(token, 0.0) for token, weight in left.items())


def question_score(text: str) -> float:
    if "?" in text:
        return 1.0
    lowered = text.lower()
    if re.search(r"\b(como|qual|porque|por que|where|what|why|how|can|does)\b", lowered):
        return 0.75
    return 0.0


def response_marker_score(text: str) -> float:
    if RESPONSE_START_RE.search(text):
        return 1.0
    score = 0.0
    if REASON_RE.search(text):
        score += 0.35
    if SECOND_PERSON_RE.search(text):
        score += 0.25
    if DISAGREEMENT_RE.search(text):
        score += 0.2
    return min(score, 1.0)


def evidence_labels(evidence: dict[str, object]) -> list[str]:
    labels: list[str] = []
    if float(evidence.get("temporal_score", 0.0) or 0.0) >= 0.6:
        labels.append("tempo")
    if float(evidence.get("semantic_similarity", 0.0) or 0.0) >= 0.25:
        labels.append("similaridade")
    if float(evidence.get("mention_score", 0.0) or 0.0) > 0:
        labels.append("mencao")
    if float(evidence.get("question_answer_score", 0.0) or 0.0) >= 0.5:
        labels.append("pergunta-resposta")
    if float(evidence.get("same_native_thread_score", 0.0) or 0.0) > 0:
        labels.append("thread-nativa")
    if float(evidence.get("participant_continuity_score", 0.0) or 0.0) >= 0.4:
        labels.append("participantes")
    if int(evidence.get("shared_technical_token_count", 0) or 0) > 0:
        labels.append("termos-tecnicos")
    return labels


def html_escape(text: object) -> str:
    return escape("" if text is None else str(text), quote=True)
