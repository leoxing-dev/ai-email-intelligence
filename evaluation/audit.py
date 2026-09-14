"""Deterministic structural audit helpers for synthetic benchmark records."""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean

from app.schemas.summary import ActionKind, Assessment, DateSemanticType, EventStatus
from evaluation.schemas import EvaluationCase


_COMMON = {
    "and", "are", "for", "from", "synthetic", "that", "the", "this", "was",
    "will", "with", "you", "your",
}
_DATE_WORDS = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?|\d+(?::\d+)?)\b",
    re.IGNORECASE,
)


def _positive_counts(case: EvaluationCase) -> dict[str, bool]:
    truth = case.ground_truth
    return {
        "required_action": truth.action_kind is ActionKind.REQUIRED,
        "contains_event": truth.contains_event,
        "upcoming_event": truth.event_status is EventStatus.UPCOMING,
        "registration_required": truth.registration_required is Assessment.TRUE,
        "registration_completed": truth.registration_completed is Assessment.TRUE,
        "deadline_detection": any(
            item.semantic_type
            in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE}
            for item in truth.dates
        ),
        "needs_reply": truth.needs_reply is Assessment.TRUE,
    }


def structural_statistics(cases: list[EvaluationCase]) -> dict[str, object]:
    """Return label balance and structure counts without retaining message text."""

    tasks = list(_positive_counts(cases[0])) if cases else []
    positives = {
        task: sum(_positive_counts(case)[task] for case in cases) for task in tasks
    }
    count = len(cases)
    return {
        "cases": count,
        "email_types": dict(sorted(Counter(c.ground_truth.email_type.value for c in cases).items())),
        "task_balance": {
            task: {"positive": value, "negative": count - value}
            for task, value in positives.items()
        },
        "routes": dict(sorted(Counter(c.ground_truth.expected_route.value for c in cases).items())),
        "tags": dict(sorted(Counter(tag for c in cases for tag in c.tags).items())),
        "average_subject_characters": mean(len(c.input.subject) for c in cases) if cases else 0,
        "average_body_characters": mean(len(c.input.body) for c in cases) if cases else 0,
        "multi_date_cases": sum(len(c.ground_truth.dates) > 1 for c in cases),
        "multi_event_cases": sum(
            sum(d.semantic_type is DateSemanticType.EVENT_TIME for d in c.ground_truth.dates) > 1
            for c in cases
        ),
        "html_or_noise_cases": sum(
            c.input.body_format == "html"
            or bool({"html_noise", "preheader", "tracking", "boilerplate"} & set(c.tags))
            for c in cases
        ),
        "digest_or_container_cases": sum(bool({"digest", "container"} & set(c.tags)) for c in cases),
        "conditional_cases": sum("conditional" in c.tags for c in cases),
        "manual_review_cases": sum(c.ground_truth.expected_route.value == "manual_review" for c in cases),
    }


def normalized_tokens(case: EvaluationCase) -> set[str]:
    text = _DATE_WORDS.sub(" ", f"{case.input.subject} {case.input.body}".casefold())
    return {
        token
        for token in re.findall(r"[a-z']+", text)
        if len(token) > 2 and token not in _COMMON
    }


def cross_split_similarities(
    left: list[EvaluationCase],
    right: list[EvaluationCase],
    *,
    threshold: float = 0.35,
) -> list[tuple[float, str, str]]:
    """Find lexical template candidates after removing names/dates/common words."""

    matches: list[tuple[float, str, str]] = []
    for first in left:
        first_tokens = normalized_tokens(first)
        for second in right:
            second_tokens = normalized_tokens(second)
            union = first_tokens | second_tokens
            similarity = len(first_tokens & second_tokens) / len(union) if union else 0
            if similarity >= threshold:
                matches.append((similarity, first.id, second.id))
    return sorted(matches, key=lambda item: (-item[0], item[1], item[2]))


def family_split_violations(
    split_cases: dict[str, list[EvaluationCase]],
) -> dict[str, list[str]]:
    families: dict[str, set[str]] = {}
    for split, cases in split_cases.items():
        for case in cases:
            if case.family_id:
                families.setdefault(case.family_id, set()).add(split)
    return {
        family: sorted(splits)
        for family, splits in sorted(families.items())
        if len(splits) > 1
    }
