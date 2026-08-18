"""Features textuais compartilhadas pelas três abordagens experimentais."""

from __future__ import annotations

import re
from collections.abc import Iterable

TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+", re.UNICODE)
RESPONSE_START_RE = re.compile(
    r"^\s*(sim|nao|não|isso|depende|tenta|verifica|use|usa|voce|você|you|try|check|yes|no)\b",
    re.IGNORECASE,
)
REASON_RE = re.compile(r"\b(porque|pois|entao|então|because|since|therefore)\b", re.IGNORECASE)
SECOND_PERSON_RE = re.compile(r"\b(voce|você|seu|sua|teu|tua|you|your)\b", re.IGNORECASE)
DISAGREEMENT_RE = re.compile(
    r"\b(mas|porem|porém|na verdade|nao e isso|não é isso|however|actually|but)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "a", "as", "and", "an", "are", "ao", "aos", "at", "be", "been", "by",
    "can", "com", "da", "das", "de", "do", "dos", "e", "em", "for", "from",
    "have", "has", "how", "i", "if", "in", "is", "it", "just", "like", "na",
    "nas", "no", "nos", "not", "o", "of", "on", "os", "or", "our", "para",
    "por", "que", "that", "there", "them", "they", "the", "this", "to", "um",
    "uma", "was", "we", "were", "what", "when", "where", "which", "will", "with",
    "would", "you", "your",
}

TECHNICAL_TERMS = {
    "api", "apoc", "async", "backend", "bug", "build", "cache", "class", "cli",
    "cluster", "code", "commit", "compile", "constraint", "cypher", "database",
    "debug", "dependency", "docker", "driver", "edge", "endpoint", "error",
    "exception", "frontend", "function", "graph", "graphql", "index", "java",
    "javascript", "json", "kubernetes", "linux", "merge", "method", "neo4j", "node",
    "npm", "package", "pip", "plugin", "python", "query", "relationship", "repo",
    "request", "response", "schema", "script", "server", "stack", "transaction",
    "traceback", "typescript", "version",
}


def tokenize(text: str) -> list[str]:
    tokens = [token.lower().strip(".") for token in TOKEN_RE.findall(text)]
    return [token for token in tokens if token and token not in STOPWORDS and token != "url"]


def technical_tokens(tokens: Iterable[str]) -> list[str]:
    result: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered in TECHNICAL_TERMS or "." in lowered or lowered.startswith(("py", "js")):
            if lowered not in result:
                result.append(lowered)
    return result


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(token, 0.0) for token, weight in left.items())


def question_score(text: str) -> float:
    if "?" in text:
        return 1.0
    if re.search(r"\b(como|qual|porque|por que|where|what|why|how|can|does)\b", text.lower()):
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
