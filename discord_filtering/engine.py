from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from functools import lru_cache
from numbers import Real
from typing import Any

from .models import (
    ChannelClassification,
    ContentSignal,
    FilterProfile,
    RuleEvidence,
    ServerClassification,
    SignalEvidence,
    SignalScore,
    WeightedRule,
)


def is_missing(value: Any) -> bool:
    """Recognize None, NaN and pandas-style NA values without importing pandas."""

    if value is None:
        return True
    if isinstance(value, str):
        return False
    if type(value).__name__ in {"NAType", "NaTType"}:
        # pandas.NA cannot be coerced to bool after a comparison, so recognize
        # its scalar sentinels without making pandas a dependency of the engine.
        return True
    try:
        comparison = value != value
        return bool(comparison)
    except (TypeError, ValueError):
        return False


def normalize_keywords(value: Any) -> tuple[str, ...]:
    """Normalize metadata keywords supplied as list, scalar string, or NA.

    A string is one keyword value rather than an iterable of characters. Empty
    and missing elements are discarded, while order is retained for auditability.
    """

    if is_missing(value):
        return ()
    raw_items: Iterable[Any]
    if isinstance(value, str):
        raw_items = (value,)
    elif isinstance(value, (list, tuple, set, frozenset)):
        raw_items = value
    else:
        raw_items = (value,)
    normalized: list[str] = []
    for item in raw_items:
        if is_missing(item):
            continue
        text = unicodedata.normalize("NFKC", str(item)).strip()
        if text and text.casefold() not in {"na", "n/a", "null"}:
            normalized.append(text)
    return tuple(normalized)


@lru_cache(maxsize=512)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


def _field_values(record: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[tuple[str, int, str], ...]:
    values: list[tuple[str, int, str]] = []
    for field in fields:
        raw = record.get(field)
        if field == "keywords":
            items = normalize_keywords(raw)
        elif isinstance(raw, (list, tuple, set, frozenset)):
            items = tuple(str(item).strip() for item in raw if not is_missing(item) and str(item).strip())
        elif is_missing(raw):
            items = ()
        else:
            text = str(raw).strip()
            items = (text,) if text else ()
        values.extend(
            (field, index, normalized)
            for index, text in enumerate(items)
            if (normalized := unicodedata.normalize("NFKC", text).strip())
        )
    return tuple(values)


def _score_rules(
    record: Mapping[str, Any],
    fields: tuple[str, ...],
    rules: tuple[WeightedRule, ...],
    overlap_policy: str,
) -> tuple[float, tuple[RuleEvidence, ...]]:
    if overlap_policy != "max_per_group":
        raise ValueError(f"unsupported overlap policy: {overlap_policy}")

    provisional: list[tuple[WeightedRule, str, int, re.Match[str]]] = []
    for field, value_index, text in _field_values(record, fields):
        for rule in rules:
            match = _compiled(rule.pattern).search(text)
            if match is not None:
                provisional.append((rule, field, value_index, match))

    winning_rule_by_group: dict[str, WeightedRule] = {}
    for rule, _field, _value_index, _match in provisional:
        winner = winning_rule_by_group.get(rule.group)
        if winner is None or rule.weight > winner.weight:
            winning_rule_by_group[rule.group] = rule

    credited_rule_ids: set[str] = set()
    evidence: list[RuleEvidence] = []
    for rule, field, value_index, match in provisional:
        winner = winning_rule_by_group[rule.group]
        credited = 0.0
        if winner.rule_id == rule.rule_id and rule.rule_id not in credited_rule_ids:
            credited = rule.weight
            credited_rule_ids.add(rule.rule_id)
        evidence.append(
            RuleEvidence(
                rule_id=rule.rule_id,
                label=rule.label,
                group=rule.group,
                field=field,
                value_index=value_index,
                matched_text=match.group(0),
                start=match.start(),
                end=match.end(),
                weight=rule.weight,
                credited_weight=credited,
            )
        )
    score = round(sum(rule.weight for rule in winning_rule_by_group.values()), 6)
    return score, tuple(evidence)


def _optional_text(value: Any) -> str | None:
    if is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _identifier_from(record: Mapping[str, Any], *fields: str) -> str:
    for field in fields:
        value = _optional_text(record.get(field))
        if value is not None:
            return value
    return ""


def _optional_text_from(record: Mapping[str, Any], *fields: str) -> str | None:
    for field in fields:
        value = _optional_text(record.get(field))
        if value is not None:
            return value
    return None


def _optional_int(value: Any) -> int | None:
    if is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _nonnegative_int(value: Any) -> int:
    parsed = _optional_int(value)
    return max(parsed or 0, 0)


def _bounded_ratio(value: Any) -> float:
    if is_missing(value):
        return 0.0
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _as_bool(value: Any) -> bool:
    if is_missing(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, Real):
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def classify_server(record: Mapping[str, Any], profile: FilterProfile) -> ServerClassification:
    """Classify one server without I/O or global state.

    All fields, patterns, weights, overlap behavior, exclusions and thresholds
    come from ``profile``. Evidence is retained per source field instead of being
    collapsed into the legacy concatenated search text.
    """

    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")
    policy = profile.server
    positive_score, positive_evidence = _score_rules(
        record,
        policy.fields,
        policy.positive_rules,
        policy.overlap_policy,
    )
    negative_score, negative_evidence = _score_rules(
        record,
        policy.fields,
        policy.negative_rules,
        policy.overlap_policy,
    )
    margin = round(positive_score - negative_score, 6)
    matched_positive_labels = {item.label for item in positive_evidence}
    matched_negative_labels = {item.label for item in negative_evidence}
    blocked = tuple(
        sorted(matched_negative_labels.intersection(policy.selection.blocked_negative_labels))
    )
    selected = (
        positive_score >= policy.selection.min_positive_score
        and margin >= policy.selection.min_score_margin
        and (
            policy.selection.max_negative_score is None
            or negative_score <= policy.selection.max_negative_score
        )
        and (
            not policy.selection.required_positive_labels
            or bool(
                matched_positive_labels.intersection(
                    policy.selection.required_positive_labels
                )
            )
        )
        and not blocked
    )

    return ServerClassification(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        domain=profile.domain,
        guild_id=_identifier_from(record, "guild_id", "server_id", "id"),
        slug=_optional_text(record.get("slug")),
        name=_optional_text(record.get("name")),
        description=_optional_text(record.get("description")),
        about=_optional_text(record.get("about")),
        reasons_to_join=normalize_keywords(record.get("reasons_to_join")),
        preferred_locale=_optional_text(record.get("preferred_locale")),
        primary_category_id=_optional_text(record.get("primary_category_id")),
        approximate_member_count=_optional_int(record.get("approximate_member_count")),
        approximate_presence_count=_optional_int(record.get("approximate_presence_count")),
        vanity_url_code=_optional_text(record.get("vanity_url_code")),
        keywords=normalize_keywords(record.get("keywords")),
        positive_score=positive_score,
        negative_score=negative_score,
        score_margin=margin,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        blocked_negative_terms=blocked,
        is_selected=selected,
    )


def _bounded_signal(count: int, total: int, saturation_ratio: float) -> float:
    if total <= 0:
        return 0.0
    return min(count / (total * saturation_ratio), 1.0)


def _message_id(message: Mapping[str, Any]) -> str | None:
    value = _identifier_from(message, "message_id", "id")
    return value or None


def _score_signal_counts(
    policy_signals: tuple[ContentSignal, ...],
    counts: Mapping[str, int],
    total: int,
    examples: Mapping[str, tuple[SignalEvidence, ...]],
) -> tuple[tuple[SignalScore, ...], float, float]:
    scores: list[SignalScore] = []
    lexical_total = 0.0
    domain_total = 0.0
    for signal in policy_signals:
        count = max(int(counts.get(signal.signal_id, 0)), 0)
        lexical_contribution = signal.lexical_weight * _bounded_signal(
            count,
            total,
            signal.lexical_saturation_ratio,
        )
        domain_contribution = signal.domain_weight * _bounded_signal(
            count,
            total,
            signal.domain_saturation_ratio,
        )
        lexical_total += lexical_contribution
        domain_total += domain_contribution
        scores.append(
            SignalScore(
                signal_id=signal.signal_id,
                label=signal.label,
                count_field=signal.count_field,
                count=count,
                lexical_contribution=round(lexical_contribution, 6),
                domain_contribution=round(domain_contribution, 6),
                evidence=examples.get(signal.signal_id, ()),
            )
        )
    return tuple(scores), round(min(lexical_total, 1.0), 6), round(min(domain_total, 1.0), 6)


def _classify_channel(
    score: float,
    lexical_score: float,
    domain_score: float,
    negative_labels: set[str],
    profile: FilterProfile,
) -> str:
    policy = profile.channel.classification
    if (
        negative_labels.intersection(policy.admin_negative_labels)
        and lexical_score < policy.admin_max_lexical_score
        and domain_score < policy.admin_max_domain_score
    ):
        return policy.class_admin
    if (
        negative_labels.intersection(policy.social_negative_labels)
        and lexical_score < policy.social_max_lexical_score
    ):
        return policy.class_social
    if score >= policy.high_confidence_score and lexical_score >= policy.high_min_lexical_score:
        return policy.class_high
    if score >= policy.review_score or (
        lexical_score >= policy.fallback_min_lexical_score
        and domain_score >= policy.fallback_min_domain_score
    ):
        return policy.class_review
    if negative_labels.intersection(policy.admin_negative_labels):
        return policy.class_admin
    return policy.class_social


def _conversation_suitability(
    *,
    n_users: int,
    n_messages: int,
    n_bot_messages: int,
    total_messages: int,
    interaction_message_count: int,
    interacting_human_user_count: int,
    author_transition_ratio: float,
    dominant_author_ratio: float,
    profile: FilterProfile,
) -> tuple[float, float, float, bool, tuple[str, ...]]:
    policy = profile.channel.conversation_suitability
    interaction_ratio = interaction_message_count / n_messages if n_messages else 0.0
    bot_message_ratio = n_bot_messages / total_messages if total_messages else 0.0
    user_score = min(n_users / policy.min_human_users, 1.0)
    interaction_score = min(interaction_ratio / policy.min_interaction_ratio, 1.0)
    transition_score = min(author_transition_ratio / policy.min_author_transition_ratio, 1.0)
    dominance_score = min(policy.max_dominant_author_ratio / dominant_author_ratio, 1.0) if dominant_author_ratio else 0.0
    conversation_score = round(
        (user_score + interaction_score + transition_score + dominance_score + (1.0 - bot_message_ratio)) / 5.0,
        6,
    )
    reasons: list[str] = []
    if n_users < policy.min_human_users:
        reasons.append("insufficient_human_users")
    if interaction_ratio < policy.min_interaction_ratio:
        reasons.append("low_interaction")
    if interacting_human_user_count < policy.min_interacting_human_users:
        reasons.append("insufficient_interacting_human_users")
    if author_transition_ratio < policy.min_author_transition_ratio:
        reasons.append("low_author_turn_taking")
    if dominant_author_ratio > policy.max_dominant_author_ratio:
        reasons.append("dominant_human_author")
    if bot_message_ratio > policy.max_bot_message_ratio:
        reasons.append("bot_dominated")
    return (
        round(interaction_ratio, 6),
        round(bot_message_ratio, 6),
        conversation_score,
        not reasons,
        tuple(reasons),
    )


def score_channel(
    record: Mapping[str, Any],
    profile: FilterProfile,
    *,
    messages: Iterable[Mapping[str, Any]] | None = None,
) -> ChannelClassification:
    """Score one channel from messages or compatible pre-aggregated counts.

    This function is deterministic and performs no reads or writes. When
    ``messages`` is omitted, ``record`` may use the current aggregate schema
    (``n_messages`` plus each profile signal's ``count_field``). Supplying raw
    messages adds bounded examples linking content evidence to message IDs.
    """

    if not isinstance(record, Mapping):
        raise TypeError("record must be a mapping")
    policy = profile.channel
    metadata_positive, positive_evidence = _score_rules(
        record,
        policy.metadata_fields,
        policy.positive_rules,
        policy.overlap_policy,
    )
    metadata_negative, negative_evidence = _score_rules(
        record,
        policy.metadata_fields,
        policy.negative_rules,
        policy.overlap_policy,
    )
    metadata_score = min(max(metadata_positive - metadata_negative, 0.0) / policy.metadata_normalization, 1.0)

    counts: dict[str, int] = {signal.signal_id: 0 for signal in policy.signals}
    evidence_lists: dict[str, list[SignalEvidence]] = {signal.signal_id: [] for signal in policy.signals}
    n_messages = 0
    n_users = 0
    n_bot_messages = 0
    total_messages = 0
    interaction_message_count = 0
    valid_native_reply_message_count = 0
    mention_interaction_message_count = 0
    interacting_human_users: set[str] = set()
    human_authors_in_order: list[str] = []
    if messages is None:
        n_messages = _nonnegative_int(record.get("n_messages"))
        n_users = _nonnegative_int(record.get("n_users"))
        n_bot_messages = _nonnegative_int(record.get("n_bot_messages"))
        total_messages = _nonnegative_int(record.get("total_messages")) or n_messages + n_bot_messages
        interaction_message_count = _nonnegative_int(record.get("interaction_message_count"))
        valid_native_reply_message_count = _nonnegative_int(record.get("valid_native_reply_message_count"))
        mention_interaction_message_count = _nonnegative_int(record.get("mention_interaction_message_count"))
        interacting_human_user_count = _nonnegative_int(record.get("interacting_human_user_count"))
        author_transition_ratio = _bounded_ratio(record.get("author_transition_ratio"))
        dominant_author_ratio = _bounded_ratio(record.get("dominant_author_ratio"))
        for signal in policy.signals:
            counts[signal.signal_id] = _nonnegative_int(record.get(signal.count_field))
    else:
        ordered_messages = sorted(
            messages,
            key=lambda item: (_optional_text(item.get("timestamp")) or "", _message_id(item) or ""),
        )
        users: set[str] = set()
        previous_human_message_ids: set[str] = set()
        for message in ordered_messages:
            if not isinstance(message, Mapping):
                raise TypeError("each message must be a mapping")
            total_messages += 1
            bot = _as_bool(message.get("is_bot"))
            if bot:
                n_bot_messages += 1
            if bot and policy.exclude_bot_messages:
                continue
            n_messages += 1
            author = _identifier_from(message, "author_id", "author_username")
            if author:
                users.add(author)
                human_authors_in_order.append(author)
            valid_reply = bool(
                _identifier_from(message, "referenced_message_id")
                and _identifier_from(message, "referenced_message_id") in previous_human_message_ids
            )
            mentioned_user = _nonnegative_int(message.get("mention_count")) > 0
            if valid_reply:
                valid_native_reply_message_count += 1
            if mentioned_user:
                mention_interaction_message_count += 1
            if valid_reply or mentioned_user:
                interaction_message_count += 1
                if author:
                    interacting_human_users.add(author)
            message_id = _message_id(message)
            if message_id:
                previous_human_message_ids.add(message_id)
            content = _optional_text(message.get("content")) or ""
            for signal in policy.signals:
                match = _compiled(signal.pattern).search(content)
                if match is None:
                    continue
                counts[signal.signal_id] += 1
                signal_examples = evidence_lists[signal.signal_id]
                if len(signal_examples) < policy.max_evidence_examples:
                    signal_examples.append(
                        SignalEvidence(
                            signal_id=signal.signal_id,
                            field="content",
                            record_id=_message_id(message),
                            matched_text=match.group(0),
                        )
                    )
        n_users = len(users)

    if messages is not None:
        interacting_human_user_count = len(interacting_human_users)
        author_counts = Counter(human_authors_in_order)
        dominant_author_ratio = max(author_counts.values(), default=0) / len(human_authors_in_order) if human_authors_in_order else 0.0
        transitions = sum(
            previous != current
            for previous, current in zip(human_authors_in_order, human_authors_in_order[1:])
        )
        author_transition_ratio = transitions / max(len(human_authors_in_order) - 1, 1)

    evidence = {key: tuple(value) for key, value in evidence_lists.items()}
    signal_scores, lexical_score, domain_score = _score_signal_counts(
        policy.signals,
        counts,
        n_messages,
        evidence,
    )
    weights = policy.component_weights
    channel_score = round(
        min(
            weights.metadata * metadata_score
            + weights.lexical * lexical_score
            + weights.domain * domain_score,
            1.0,
        ),
        6,
    )
    metadata_score = round(metadata_score, 6)
    negative_labels = {item.label for item in negative_evidence}
    channel_class = _classify_channel(
        channel_score,
        lexical_score,
        domain_score,
        negative_labels,
        profile,
    )
    (
        interaction_ratio,
        bot_message_ratio,
        conversation_score,
        conversation_suitable,
        conversation_exclusion_reasons,
    ) = _conversation_suitability(
        n_users=n_users,
        n_messages=n_messages,
        n_bot_messages=n_bot_messages,
        total_messages=total_messages,
        interaction_message_count=interaction_message_count,
        interacting_human_user_count=interacting_human_user_count,
        author_transition_ratio=author_transition_ratio,
        dominant_author_ratio=dominant_author_ratio,
        profile=profile,
    )
    classification_policy = policy.classification
    return ChannelClassification(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        domain=profile.domain,
        guild_id=_identifier_from(record, "guild_id", "server_id"),
        guild_name=_optional_text_from(record, "guild_name", "server_name"),
        channel_id=_identifier_from(record, "channel_id", "id"),
        channel_name=_optional_text_from(record, "channel_name", "name"),
        n_messages=n_messages,
        n_users=n_users,
        n_bot_messages=n_bot_messages,
        total_messages=total_messages,
        interaction_message_count=interaction_message_count,
        valid_native_reply_message_count=valid_native_reply_message_count,
        mention_interaction_message_count=mention_interaction_message_count,
        interacting_human_user_count=interacting_human_user_count,
        interaction_ratio=interaction_ratio,
        author_transition_ratio=round(author_transition_ratio, 6),
        dominant_author_ratio=round(dominant_author_ratio, 6),
        bot_message_ratio=bot_message_ratio,
        conversation_score=conversation_score,
        conversation_suitable=conversation_suitable,
        conversation_exclusion_reasons=conversation_exclusion_reasons,
        metadata_positive_score=metadata_positive,
        metadata_negative_score=metadata_negative,
        metadata_score=metadata_score,
        lexical_evidence_score=lexical_score,
        domain_evidence_score=domain_score,
        channel_score=channel_score,
        channel_class=channel_class,
        include_in_main_analysis=(
            channel_class in classification_policy.include_classes
            and conversation_suitable
        ),
        manual_review_required=(
            channel_class in classification_policy.manual_review_classes
            or (
                channel_class in classification_policy.include_classes
                and not conversation_suitable
            )
        ),
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        signal_scores=signal_scores,
        score_field=policy.score_field,
        domain_score_field=policy.domain_score_field,
    )
