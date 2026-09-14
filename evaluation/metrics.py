"""Reusable, threshold-free evaluation metrics for classifier predictions."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Callable, Iterable

from app.schemas.summary import ActionKind, Assessment, DateSemanticType, EventStatus
from evaluation import BASELINE_ID
from evaluation.dataset import dataset_fingerprint
from evaluation.schemas import (
    AbstentionMetrics,
    BinaryMetrics,
    CaseFailure,
    CasePrediction,
    DateMetrics,
    EvaluationCase,
    EvaluationReport,
    EvaluationRoute,
    ExpectedDate,
    PredictedDate,
    ProtectedMetrics,
    TagMetrics,
)


BinarySelector = Callable[[EvaluationCase, CasePrediction], tuple[bool, bool]]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def binary_metrics(actual: Iterable[bool], predicted: Iterable[bool]) -> BinaryMetrics:
    pairs = list(zip(actual, predicted, strict=True))
    tp = sum(expected and observed for expected, observed in pairs)
    fp = sum(not expected and observed for expected, observed in pairs)
    fn = sum(expected and not observed for expected, observed in pairs)
    tn = sum(not expected and not observed for expected, observed in pairs)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return BinaryMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def _binary_selectors() -> dict[str, BinarySelector]:
    return {
        "required_action": lambda case, prediction: (
            case.ground_truth.action_kind is ActionKind.REQUIRED,
            prediction.action_kind is ActionKind.REQUIRED,
        ),
        "contains_event": lambda case, prediction: (
            case.ground_truth.contains_event,
            prediction.contains_event,
        ),
        "upcoming_event": lambda case, prediction: (
            case.ground_truth.event_status is EventStatus.UPCOMING,
            prediction.event_status is EventStatus.UPCOMING,
        ),
        "registration_required": lambda case, prediction: (
            case.ground_truth.registration_required is Assessment.TRUE,
            prediction.registration_required is Assessment.TRUE,
        ),
        "registration_completed": lambda case, prediction: (
            case.ground_truth.registration_completed is Assessment.TRUE,
            prediction.registration_completed is Assessment.TRUE,
        ),
        "deadline_detection": lambda case, prediction: (
            any(
                item.semantic_type
                in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE}
                for item in case.ground_truth.dates
            ),
            any(
                item.semantic_type
                in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE}
                for item in prediction.dates
            ),
        ),
        "needs_reply": lambda case, prediction: (
            case.ground_truth.needs_reply is Assessment.TRUE,
            prediction.needs_reply is Assessment.TRUE,
        ),
    }


def compute_binary_metrics(
    cases: list[EvaluationCase], predictions: list[CasePrediction]
) -> dict[str, BinaryMetrics]:
    by_id = {prediction.id: prediction for prediction in predictions}
    output: dict[str, BinaryMetrics] = {}
    for name, selector in _binary_selectors().items():
        pairs = [selector(case, by_id[case.id]) for case in cases]
        output[name] = binary_metrics(
            (actual for actual, _ in pairs),
            (predicted for _, predicted in pairs),
        )
    return output


def route_confusion(
    cases: list[EvaluationCase], predictions: list[CasePrediction]
) -> dict[str, dict[str, int]]:
    labels = list(EvaluationRoute)
    matrix = {
        expected.value: {predicted.value: 0 for predicted in labels}
        for expected in labels
    }
    by_id = {prediction.id: prediction for prediction in predictions}
    for case in cases:
        matrix[case.ground_truth.expected_route.value][by_id[case.id].route.value] += 1
    return matrix


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _exact_equal(expected: date | datetime, predicted: date | datetime) -> bool:
    if isinstance(expected, datetime) != isinstance(predicted, datetime):
        return False
    if isinstance(expected, datetime) and isinstance(predicted, datetime):
        if expected.tzinfo is not None and predicted.tzinfo is not None:
            return expected.astimezone(UTC) == predicted.astimezone(UTC)
    return expected == predicted


def _within_tolerance(
    expected: datetime, predicted: datetime, tolerance: timedelta
) -> bool:
    if expected.tzinfo is not None and predicted.tzinfo is not None:
        expected = expected.astimezone(UTC)
        predicted = predicted.astimezone(UTC)
    return abs(expected - predicted) <= tolerance


def compute_date_metrics(
    cases: list[EvaluationCase],
    predictions: list[CasePrediction],
    *,
    tolerance_minutes: int = 15,
) -> DateMetrics:
    by_id = {prediction.id: prediction for prediction in predictions}
    expected_count = 0
    predicted_count = 0
    date_matches = 0
    exact_matches = 0
    timed_expected = 0
    tolerance_matches = 0
    tolerance = timedelta(minutes=tolerance_minutes)

    for case in cases:
        expected = case.ground_truth.dates
        predicted = [item for item in by_id[case.id].dates if item.value is not None]
        expected_count += len(expected)
        predicted_count += len(predicted)
        unused = set(range(len(predicted)))
        for expected_item in expected:
            candidates = [
                index
                for index in unused
                if _as_date(predicted[index].value) == _as_date(expected_item.value)  # type: ignore[arg-type]
            ]
            if candidates:
                index = candidates[0]
                unused.remove(index)
                date_matches += 1
                if _exact_equal(expected_item.value, predicted[index].value):  # type: ignore[arg-type]
                    exact_matches += 1

            if isinstance(expected_item.value, datetime):
                timed_expected += 1
                timed_candidate = next(
                    (
                        item
                        for item in predicted
                        if isinstance(item.value, datetime)
                        and _within_tolerance(expected_item.value, item.value, tolerance)
                    ),
                    None,
                )
                if timed_candidate is not None:
                    tolerance_matches += 1

    return DateMetrics(
        expected_count=expected_count,
        predicted_count=predicted_count,
        date_only_match_count=date_matches,
        extraction_precision=_ratio(date_matches, predicted_count),
        extraction_recall=_ratio(date_matches, expected_count),
        exact_normalized_match_count=exact_matches,
        exact_normalized_match_rate=_ratio(exact_matches, expected_count),
        timed_expected_count=timed_expected,
        time_tolerance_match_count=tolerance_matches,
        time_tolerance_accuracy=_ratio(tolerance_matches, timed_expected),
        tolerance_minutes=tolerance_minutes,
    )


def _case_differences(
    case: EvaluationCase, prediction: CasePrediction
) -> tuple[dict[str, object], dict[str, object]]:
    truth = case.ground_truth
    pairs: dict[str, tuple[object, object]] = {
        "email_type": (truth.email_type.value, prediction.email_type.value),
        "action_kind": (truth.action_kind.value, prediction.action_kind.value),
        "needs_reply": (truth.needs_reply.value, prediction.needs_reply.value),
        "contains_event": (truth.contains_event, prediction.contains_event),
        "event_status": (truth.event_status.value, prediction.event_status.value),
        "registration_available": (
            truth.registration_available.value,
            prediction.registration_available.value,
        ),
        "registration_required": (
            truth.registration_required.value,
            prediction.registration_required.value,
        ),
        "registration_completed": (
            truth.registration_completed.value,
            prediction.registration_completed.value,
        ),
        "route": (truth.expected_route.value, prediction.route.value),
        "dates": (
            sorted(
                f"{item.value}|{item.semantic_type.value}" for item in truth.dates
            ),
            sorted(
                f"{item.value}|{item.semantic_type.value}"
                for item in prediction.dates
                if item.value is not None
            ),
        ),
    }
    expected = {name: values[0] for name, values in pairs.items() if values[0] != values[1]}
    predicted = {name: values[1] for name, values in pairs.items() if values[0] != values[1]}
    return expected, predicted


def evaluate(
    cases: list[EvaluationCase],
    predictions: list[CasePrediction],
    *,
    dataset_version: str,
    split: str,
    split_counts: dict[str, int],
    tolerance_minutes: int = 15,
    baseline_id: str = BASELINE_ID,
) -> EvaluationReport:
    if {case.id for case in cases} != {prediction.id for prediction in predictions}:
        raise ValueError("cases and predictions must have identical IDs")
    by_id = {prediction.id: prediction for prediction in predictions}
    binary = compute_binary_metrics(cases, predictions)
    confusion = route_confusion(cases, predictions)
    route_correct = sum(
        case.ground_truth.expected_route is by_id[case.id].route for case in cases
    )
    accepted_cases = [
        case for case in cases if by_id[case.id].route is not EvaluationRoute.MANUAL_REVIEW
    ]
    accepted_errors = sum(
        case.ground_truth.expected_route is not by_id[case.id].route
        for case in accepted_cases
    )
    required = binary["required_action"]
    upcoming = binary["upcoming_event"]
    deadline = binary["deadline_detection"]

    by_tag: dict[str, TagMetrics] = {}
    for tag in sorted({tag for case in cases for tag in case.tags}):
        tag_cases = [case for case in cases if tag in case.tags]
        tag_predictions = [by_id[case.id] for case in tag_cases]
        tag_route_correct = sum(
            case.ground_truth.expected_route is by_id[case.id].route
            for case in tag_cases
        )
        by_tag[tag] = TagMetrics(
            cases=len(tag_cases),
            route_correct=tag_route_correct,
            route_accuracy=_ratio(tag_route_correct, len(tag_cases)),
            binary_metrics=compute_binary_metrics(tag_cases, tag_predictions),
            date_metrics=compute_date_metrics(
                tag_cases, tag_predictions, tolerance_minutes=tolerance_minutes
            ),
        )

    failures: list[CaseFailure] = []
    for case in cases:
        expected, predicted = _case_differences(case, by_id[case.id])
        if expected:
            failures.append(
                CaseFailure(
                    id=case.id,
                    tags=case.tags,
                    expected=expected,
                    predicted=predicted,
                )
            )

    return EvaluationReport(
        baseline_id=baseline_id,
        dataset_version=dataset_version,
        dataset_fingerprint=dataset_fingerprint(cases),
        split=split,
        case_count=len(cases),
        split_counts=split_counts,
        binary_metrics=binary,
        route_labels=list(EvaluationRoute),
        route_confusion=confusion,
        route_accuracy=_ratio(route_correct, len(cases)),
        date_metrics=compute_date_metrics(
            cases, predictions, tolerance_minutes=tolerance_minutes
        ),
        abstention=AbstentionMetrics(
            total=len(cases),
            accepted=len(accepted_cases),
            abstained=len(cases) - len(accepted_cases),
            coverage=_ratio(len(accepted_cases), len(cases)),
            accepted_route_errors=accepted_errors,
            error_rate_among_accepted=_ratio(accepted_errors, len(accepted_cases)),
        ),
        protected_metrics=ProtectedMetrics(
            false_required_action_count=required.fp,
            false_required_action_rate=_ratio(required.fp, required.fp + required.tn),
            required_action_false_negative_count=required.fn,
            upcoming_event_false_negative_count=upcoming.fn,
            deadline_false_negative_count=deadline.fn,
        ),
        by_tag=by_tag,
        predictions=sorted(predictions, key=lambda item: item.id),
        failures=failures,
    )
