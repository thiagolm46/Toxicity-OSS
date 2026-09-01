"""Gera checkpoints leves a partir do corpus Ubuntu IRC de Kummerfeld et al.

O checkpoint Chi-inspired usa somente a ordem e o texto dos logs, ignorando por
completo os arquivos de annotation. O checkpoint IRC Transfer usa reply edges do
treino IRC. Nenhum dos dois lê dados Discord.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from discord_disentanglement.approaches.base import PREDICTION_FEATURE_COLUMNS
from discord_disentanglement.approaches.math_utils import LogisticModel, fit_logistic_regression
from discord_disentanglement.features import question_score, response_marker_score, technical_tokens, tokenize

MESSAGE_RE = re.compile(r"^\[(\d{2}):(\d{2})\]\s+<([^>]+)>\s?(.*)$")
IRC_SOURCE_COMMIT = "82ed04f9627a45d0d6f2ec3c8683c88eb408a0d5"


@dataclass(frozen=True, slots=True)
class IrcMessage:
    message_id: int
    author: str
    text: str
    seconds: float
    tokens: frozenset[str]
    technical: frozenset[str]
    vector: dict[str, float]


@dataclass(frozen=True, slots=True)
class IrcSession:
    name: str
    messages: tuple[IrcMessage, ...]
    parents_by_child: dict[int, tuple[int, ...]]


def train_external_checkpoints(
    irc_repository: Path,
    output_dir: Path,
    *,
    seed: int = 42,
    maximum_sessions: int | None = None,
) -> tuple[Path, Path]:
    train_dir = Path(irc_repository) / "data" / "train"
    unlabeled_sessions = load_sessions(
        train_dir, maximum_sessions=maximum_sessions, include_annotations=False
    )
    supervised_sessions = load_sessions(
        train_dir, maximum_sessions=maximum_sessions, include_annotations=True
    )
    if len(unlabeled_sessions) < 2 or len(supervised_sessions) < 2:
        raise ValueError("O treino externo requer ao menos duas sessoes IRC")
    output_dir.mkdir(parents=True, exist_ok=True)

    chi_model, chi_summary = _train_chi_inspired(unlabeled_sessions, seed=seed)
    irc_model, irc_summary = _train_irc_supervised(supervised_sessions)
    source = {
        "dataset": "Kummerfeld et al. Ubuntu IRC train split",
        "repository": "https://github.com/jkkummerfeld/irc-disentanglement",
        "source_commit": IRC_SOURCE_COMMIT,
        "data_license": "CC-BY-4.0",
    }
    common = {
        "schema_version": "1.0",
        "feature_columns": list(PREDICTION_FEATURE_COLUMNS),
    }
    chi_payload = {
        **common,
        "approach_id": "chi_zero_shot",
        "implementation_type": "INSPIRED_BY",
        "source": {
            **source,
            "raw_train_files_sha256": _source_hash(train_dir, "*.ascii.txt"),
            "annotation_files_read": 0,
        },
        "model": _serialize_model(chi_model),
        "training": chi_summary,
    }
    irc_payload = {
        **common,
        "approach_id": "irc_transfer",
        "implementation_type": "INSPIRED_BY",
        "source": {
            **source,
            "raw_and_annotation_train_files_sha256": _source_hash(train_dir, "*.txt"),
            "annotation_files_read": len(supervised_sessions),
        },
        "model": _serialize_model(irc_model),
        "training": irc_summary,
    }
    chi_path = output_dir / "chi_zero_shot.irc_self_supervised.v1.json"
    irc_path = output_dir / "irc_transfer.kummerfeld2019.v1.json"
    chi_path.write_text(json.dumps(chi_payload, indent=2, sort_keys=True), encoding="utf-8")
    irc_path.write_text(json.dumps(irc_payload, indent=2, sort_keys=True), encoding="utf-8")
    return chi_path, irc_path


def load_sessions(
    train_dir: Path,
    *,
    maximum_sessions: int | None = None,
    include_annotations: bool = True,
) -> list[IrcSession]:
    ascii_paths = sorted(Path(train_dir).glob("*.ascii.txt"))
    if maximum_sessions is not None:
        ascii_paths = ascii_paths[:maximum_sessions]
    sessions: list[IrcSession] = []
    for ascii_path in ascii_paths:
        raw_messages = _parse_ascii(ascii_path)
        if len(raw_messages) < 3:
            continue
        parents_by_child_lists: defaultdict[int, list[int]] = defaultdict(list)
        if include_annotations:
            annotation_path = ascii_path.with_name(
                ascii_path.name.replace(".ascii.txt", ".annotation.txt")
            )
            if not annotation_path.exists():
                continue
            for line in annotation_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                fields = line.split()
                if len(fields) < 2:
                    continue
                parents_by_child_lists[int(fields[1])].append(int(fields[0]))
        parents_by_child = {
            child_id: tuple(parent_ids)
            for child_id, parent_ids in parents_by_child_lists.items()
        }
        sessions.append(
            IrcSession(
                name=ascii_path.name,
                messages=tuple(raw_messages),
                parents_by_child=parents_by_child,
            )
        )
    return sessions


def _parse_ascii(path: Path) -> list[IrcMessage]:
    parsed: list[tuple[int, str, str, float, list[str]]] = []
    day_offset = 0.0
    previous_seconds: float | None = None
    for raw_position, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        match = MESSAGE_RE.match(line)
        if match is None:
            continue
        seconds = int(match.group(1)) * 3600.0 + int(match.group(2)) * 60.0
        if previous_seconds is not None and seconds + day_offset < previous_seconds - 12 * 3600:
            day_offset += 24 * 3600.0
        seconds += day_offset
        previous_seconds = seconds
        text = match.group(4)
        parsed.append(
            (1000 + raw_position, match.group(3).casefold(), text, seconds, tokenize(text))
        )
    document_frequency = Counter(
        token for _, _, _, _, tokens in parsed for token in set(tokens)
    )
    count = max(1, len(parsed))
    messages: list[IrcMessage] = []
    for message_id, author, text, seconds, tokens in parsed:
        counts = Counter(tokens)
        weights = {
            token: value * (math.log((1 + count) / (1 + document_frequency[token])) + 1.0)
            for token, value in counts.items()
        }
        norm = math.sqrt(sum(value * value for value in weights.values())) or 1.0
        messages.append(
            IrcMessage(
                message_id=message_id,
                author=author,
                text=text,
                seconds=seconds,
                tokens=frozenset(tokens),
                technical=frozenset(technical_tokens(tokens)),
                vector={token: value / norm for token, value in weights.items()},
            )
        )
    return messages


def _pair_features(source: IrcMessage, target: IrcMessage, lag: int) -> np.ndarray:
    delta = max(1.0, source.seconds - target.seconds)
    same_author = source.author == target.author
    source_text = source.text.casefold()
    target_text = target.text.casefold()
    return np.asarray(
        [
            math.exp(-delta / 7200.0),
            _cosine(source.vector, target.vector),
            _jaccard(source.tokens, target.tokens),
            float(_mentions(source_text, target.author)),
            float(_mentions(target_text, source.author)),
            float(lag == 1),
            float(not same_author),
            float(same_author),
            question_score(target.text) * max(response_marker_score(source.text), 0.35),
            _jaccard(source.technical, target.technical),
            _length_similarity(source.tokens, target.tokens),
            1.0 / max(1, lag),
        ],
        dtype=np.float64,
    )


def _train_chi_inspired(
    sessions: list[IrcSession], *, seed: int
) -> tuple[LogisticModel, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    features: list[np.ndarray] = []
    labels: list[float] = []
    maximum_bags = 30_000
    for session_index, session in enumerate(sessions):
        other = sessions[(session_index + 1) % len(sessions)]
        for source_position in range(5, len(session.messages), 3):
            source = session.messages[source_position]
            context = session.messages[max(0, source_position - 20) : source_position]
            positive_bag = np.vstack(
                [
                    _pair_features(source, target, len(context) - position)
                    for position, target in enumerate(context)
                ]
            )
            negative_source = other.messages[int(rng.integers(0, len(other.messages)))]
            negative_bag = np.vstack(
                [
                    _pair_features(negative_source, target, len(context) - position)
                    for position, target in enumerate(context)
                ]
            )
            # Feature-wise max is a small, inspectable approximation to the paper's
            # learned attention over context utterances.
            features.extend([positive_bag.max(axis=0), negative_bag.max(axis=0)])
            labels.extend([1.0, 0.0])
            if len(labels) >= maximum_bags * 2:
                break
        if len(labels) >= maximum_bags * 2:
            break
    model = fit_logistic_regression(
        np.vstack(features), np.asarray(labels), epochs=240, learning_rate=0.08, l2_penalty=2e-3
    )
    return model, {
        "regime": "self_supervised_entangled_context_response_selection",
        "annotation_files_read": 0,
        "reply_labels_used": 0,
        "irc_sessions": int(len(sessions)),
        "parsed_chat_messages": int(sum(len(session.messages) for session in sessions)),
        "response_selection_bags": int(len(labels)),
        "positive_context_definition": "chronologically preceding IRC context",
        "negative_response_definition": "response sampled from a different IRC session",
        "attention_adapter": "featurewise_max_bag_training_then_individual_pair_logit",
        "seed": seed,
    }


def _train_irc_supervised(sessions: list[IrcSession]) -> tuple[LogisticModel, dict[str, Any]]:
    differences: list[np.ndarray] = []
    edges_seen = 0
    edges_with_candidate = 0
    annotation_rows_loaded = sum(
        len(parent_ids)
        for session in sessions
        for parent_ids in session.parents_by_child.values()
    )
    annotation_rows_processed = 0
    self_links_skipped = 0
    endpoints_not_parsed_chat = 0
    non_past_or_outside_window = 0
    maximum_differences = 120_000
    for session in sessions:
        messages = session.messages
        message_by_id = {message.message_id: message for message in messages}
        position_by_id = {
            message.message_id: position for position, message in enumerate(messages)
        }
        for child_id, parent_ids in sorted(session.parents_by_child.items()):
            if child_id not in message_by_id:
                annotation_rows_processed += len(parent_ids)
                endpoints_not_parsed_chat += len(parent_ids)
                continue
            child_position = position_by_id[child_id]
            valid_parent_positions = {
                position_by_id[parent_id]
                for parent_id in parent_ids
                if parent_id != child_id and parent_id in position_by_id
            }
            for parent_id in parent_ids:
                annotation_rows_processed += 1
                if child_id == parent_id:
                    self_links_skipped += 1
                    continue
                if parent_id not in message_by_id:
                    endpoints_not_parsed_chat += 1
                    continue
                edges_seen += 1
                parent_position = position_by_id[parent_id]
                if parent_position >= child_position or child_position - parent_position > 50:
                    non_past_or_outside_window += 1
                    continue
                source = message_by_id[child_id]
                positive = _pair_features(
                    source, message_by_id[parent_id], child_position - parent_position
                )
                negative_positions = [
                    candidate_position
                    for candidate_position in range(
                        max(0, child_position - 20), child_position
                    )
                    if candidate_position not in valid_parent_positions
                ][-6:]
                if not negative_positions:
                    continue
                edges_with_candidate += 1
                for negative_position in negative_positions:
                    differences.append(
                        positive
                        - _pair_features(
                            source,
                            messages[negative_position],
                            child_position - negative_position,
                        )
                    )
                    if len(differences) >= maximum_differences:
                        break
                if len(differences) >= maximum_differences:
                    break
            if len(differences) >= maximum_differences:
                break
        if len(differences) >= maximum_differences:
            break
    positive = np.vstack(differences)
    training_x = np.vstack([positive, -positive])
    training_y = np.concatenate([np.ones(len(positive)), np.zeros(len(positive))])
    model = fit_logistic_regression(
        training_x, training_y, epochs=260, learning_rate=0.08, l2_penalty=1e-3
    )
    return model, {
        "regime": "supervised_pairwise_irc_reply_ranking",
        "irc_sessions": int(len(sessions)),
        "parsed_chat_messages": int(sum(len(session.messages) for session in sessions)),
        "annotation_rows_loaded": annotation_rows_loaded,
        "annotation_rows_processed_before_training_cap": annotation_rows_processed,
        "multiple_parents_preserved": True,
        "self_links_skipped_as_conversation_roots": self_links_skipped,
        "annotation_edges_with_unparsed_system_endpoint": endpoints_not_parsed_chat,
        "irc_reply_edges_seen": edges_seen,
        "non_past_or_outside_50_message_window": non_past_or_outside_window,
        "irc_reply_edges_with_common_window_candidate": edges_with_candidate,
        "pairwise_differences": int(len(differences)),
        "negative_candidates_per_positive_cap": 6,
        "discord_fine_tuning": False,
        "seed": 42,
    }


def _serialize_model(model: LogisticModel) -> dict[str, Any]:
    return {
        "weights": model.weights.tolist(),
        "bias": model.bias,
        "feature_mean": model.feature_mean.tolist(),
        "feature_scale": model.feature_scale.tolist(),
    }


def _source_hash(train_dir: Path, pattern: str) -> str:
    digest = hashlib.sha256()
    for path in sorted(train_dir.glob(pattern)):
        digest.update(path.name.encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(weight * right.get(token, 0.0) for token, weight in left.items())


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def _length_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return min(len(left), len(right)) / max(len(left), len(right))


def _mentions(text: str, author: str) -> bool:
    return bool(author and re.search(rf"(?<!\w){re.escape(author)}(?!\w)", text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--irc-repository", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum-sessions", type=int)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    paths = train_external_checkpoints(
        args.irc_repository,
        args.output_dir,
        seed=args.seed,
        maximum_sessions=args.maximum_sessions,
    )
    print("\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
