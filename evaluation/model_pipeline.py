"""Provider-neutral model-only evaluation over synthetic fixtures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from statistics import mean, median

from pydantic import ValidationError

from app.ai.base import ModelExtractor
from app.ai.routing import normalize_primary_route
from app.ai.schemas import (
    ProviderOutcome,
    ProviderResult,
    ProviderStatus,
    SyntheticEmailRecord,
    ValidationIssue,
    ValidationStage,
    coarse_status_for_outcome,
    validation_issues_from_error,
)
from app.schemas.summary import ActionKind, Assessment, EmailType, EventStatus
from evaluation.dataset import dataset_fingerprint
from evaluation.metrics import evaluate
from evaluation.model_schemas import (
    ConfidencePrecision,
    ExperimentTelemetry,
    ModelCaseResult,
    ModelExperimentSnapshot,
)
from evaluation.schemas import CasePrediction, EvaluationCase, EvaluationRoute, PredictedDate


def abstention_prediction(case_id: str) -> CasePrediction:
    return CasePrediction(
        id=case_id,
        email_type=EmailType.UNKNOWN,
        action_kind=ActionKind.UNCERTAIN,
        needs_reply=Assessment.UNCERTAIN,
        contains_event=False,
        event_status=EventStatus.UNCERTAIN,
        registration_available=Assessment.UNCERTAIN,
        registration_required=Assessment.UNCERTAIN,
        registration_completed=Assessment.UNCERTAIN,
        dates=[],
        route=EvaluationRoute.MANUAL_REVIEW,
    )


def case_to_model_record(case: EvaluationCase, *, timezone_name: str) -> SyntheticEmailRecord:
    return SyntheticEmailRecord(
        source="synthetic-email-benchmark-v2",
        case_id=case.id,
        subject=case.input.subject,
        body=case.input.body,
        received_at=case.input.received_at,
        timezone=timezone_name,
        sender=case.input.sender,
        body_format=case.input.body_format,
        labels=case.input.labels,
    )


def provider_result_to_case(case_id: str, result: ProviderResult) -> ModelCaseResult:
    output = result.prediction
    status = result.status
    outcome = result.outcome or ProviderOutcome.PROVIDER_FAILURE
    error_code = result.error_code
    validation_errors = list(result.validation_errors)
    if result.status is not ProviderStatus.VALID or output is None:
        prediction = abstention_prediction(case_id)
        confidence = 0.0
    else:
        try:
            route_decision = normalize_primary_route(output)
            prediction = CasePrediction(
                id=case_id,
                email_type=output.email_type,
                action_kind=output.action_kind,
                needs_reply=output.needs_reply,
                contains_event=output.contains_event,
                event_status=output.event_status,
                registration_available=output.registration_available,
                registration_required=output.registration_required,
                registration_completed=output.registration_completed,
                dates=[
                    PredictedDate(value=item.value, semantic_type=item.semantic_type)
                    for item in output.dates
                ],
                route=EvaluationRoute(route_decision.final.value),
                model_proposed_route=EvaluationRoute(route_decision.proposed.value),
            )
            confidence = output.confidence
        except (AttributeError, ValidationError, ValueError, TypeError) as exc:
            prediction = abstention_prediction(case_id)
            confidence = 0.0
            outcome = ProviderOutcome.NORMALIZATION_FAILURE
            status = coarse_status_for_outcome(outcome)
            error_code = "normalization_failure"
            if isinstance(exc, ValidationError):
                validation_errors = validation_issues_from_error(
                    exc, stage=ValidationStage.NORMALIZATION
                )
            else:
                validation_errors = [
                    ValidationIssue(
                        stage=ValidationStage.NORMALIZATION,
                        field="$",
                        received_type=type(exc).__name__,
                        expected="provider prediction compatible with evaluation schema",
                        validation_error="normalization_error",
                    )
                ]
    return ModelCaseResult(
        case_id=case_id,
        status=status,
        outcome=outcome,
        prediction=prediction,
        confidence=confidence,
        latency_ms=result.latency_ms,
        usage=result.usage,
        estimated_cost_usd=result.estimated_cost_usd,
        error_code=error_code,
        validation_errors=validation_errors,
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _telemetry(
    cases: list[EvaluationCase],
    results: list[ModelCaseResult],
    *,
    provider_calls: bool = True,
) -> ExperimentTelemetry:
    truth = {case.id: case for case in cases}
    valid = [item for item in results if item.status is ProviderStatus.VALID]
    billable = [item for item in results if item.usage.reported] if provider_calls else []
    latencies = [item.latency_ms for item in results] if provider_calls else []
    billable_costs_complete = all(
        item.estimated_cost_usd is not None for item in billable
    )
    total_cost = (
        sum(item.estimated_cost_usd or 0 for item in billable)
        if billable and billable_costs_complete
        else None
    )
    outcomes = [item.outcome or ProviderOutcome.PROVIDER_FAILURE for item in results]
    request_success_outcomes = {
        ProviderOutcome.PROVIDER_REFUSAL,
        ProviderOutcome.STRUCTURED_OUTPUT_FAILURE,
        ProviderOutcome.DOMAIN_VALIDATION_FAILURE,
        ProviderOutcome.NORMALIZATION_FAILURE,
        ProviderOutcome.MODEL_ABSTENTION,
        ProviderOutcome.VALID_PREDICTION,
    }
    structured_success_outcomes = {
        ProviderOutcome.DOMAIN_VALIDATION_FAILURE,
        ProviderOutcome.NORMALIZATION_FAILURE,
        ProviderOutcome.MODEL_ABSTENTION,
        ProviderOutcome.VALID_PREDICTION,
    }
    domain_success_outcomes = {
        ProviderOutcome.NORMALIZATION_FAILURE,
        ProviderOutcome.MODEL_ABSTENTION,
        ProviderOutcome.VALID_PREDICTION,
    }
    request_success_count = (
        sum(item in request_success_outcomes for item in outcomes)
        if provider_calls
        else 0
    )
    structured_success_count = (
        sum(item in structured_success_outcomes for item in outcomes)
        if provider_calls
        else 0
    )
    domain_success_count = (
        sum(item in domain_success_outcomes for item in outcomes)
        if provider_calls
        else 0
    )
    total_input_tokens = sum(item.usage.input_tokens for item in billable)
    total_output_tokens = sum(item.usage.output_tokens for item in billable)
    total_reasoning_tokens = sum(item.usage.reasoning_tokens for item in billable)
    confidence_metrics: list[ConfidencePrecision] = []
    for threshold in (0.70, 0.80, 0.90):
        positives = [
            item for item in valid
            if item.confidence >= threshold
            and item.prediction.action_kind is ActionKind.REQUIRED
        ]
        tp = sum(
            truth[item.case_id].ground_truth.action_kind is ActionKind.REQUIRED
            for item in positives
        )
        fp = len(positives) - tp
        confidence_metrics.append(
            ConfidencePrecision(
                threshold=threshold,
                predicted_positive=len(positives),
                true_positive=tp,
                false_positive=fp,
                precision=tp / len(positives) if positives else None,
            )
        )
    return ExperimentTelemetry(
        total_cases=len(results),
        external_request_count=len(results) if provider_calls else 0,
        reused_prediction_count=0 if provider_calls else len(results),
        valid_count=len(valid),
        abstention_count=sum(item.status is ProviderStatus.ABSTAINED for item in results),
        malformed_count=sum(item.status is ProviderStatus.MALFORMED for item in results),
        provider_failure_count=sum(item.status is ProviderStatus.FAILED for item in results),
        outcome_counts={
            outcome.value: outcomes.count(outcome) for outcome in ProviderOutcome
        },
        request_success_count=request_success_count,
        request_success_rate=(
            request_success_count / len(results)
            if provider_calls and results
            else None
        ),
        structured_output_success_count=structured_success_count,
        structured_output_success_rate=(
            structured_success_count / request_success_count
            if request_success_count
            else None
        ),
        domain_validation_success_count=domain_success_count,
        domain_validation_success_rate=(
            domain_success_count / structured_success_count
            if structured_success_count
            else None
        ),
        usable_prediction_count=len(valid),
        usable_prediction_rate=len(valid) / len(results) if results else None,
        billable_attempt_count=len(billable),
        average_latency_ms=mean(latencies) if latencies else None,
        p50_latency_ms=median(latencies) if latencies else None,
        p95_latency_ms=_percentile(latencies, 0.95),
        average_input_tokens=(
            mean(item.usage.input_tokens for item in billable) if billable else None
        ),
        average_output_tokens=(
            mean(item.usage.output_tokens for item in billable) if billable else None
        ),
        average_total_tokens=mean(
            item.usage.input_tokens + item.usage.output_tokens for item in billable
        ) if billable else None,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_tokens=total_input_tokens + total_output_tokens,
        total_reasoning_tokens=total_reasoning_tokens,
        estimated_total_cost_usd=total_cost,
        estimated_cost_per_1000_emails_usd=(
            total_cost / len(billable) * 1000
            if total_cost is not None and billable
            else None
        ),
        cost_accounting_complete=bool(billable) and billable_costs_complete,
        required_action_precision_by_confidence=confidence_metrics,
    )


def run_model_experiment(
    cases: list[EvaluationCase],
    *,
    extractor: ModelExtractor,
    timezone_name: str,
    dataset_version: str,
    split: str,
    split_counts: dict[str, int],
    max_workers: int = 1,
) -> ModelExperimentSnapshot:
    records = [case_to_model_record(case, timezone_name=timezone_name) for case in cases]
    if max_workers == 1:
        provider_results = [extractor.extract(record) for record in records]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            provider_results = list(pool.map(extractor.extract, records))
    case_results = [
        provider_result_to_case(case.id, result)
        for case, result in zip(cases, provider_results, strict=True)
    ]
    predictions = [item.prediction for item in case_results]
    end_to_end_report = evaluate(
        cases,
        predictions,
        dataset_version=dataset_version,
        split=split,
        split_counts=split_counts,
        baseline_id="model-only-v1",
    )
    usable_ids = {
        item.case_id for item in case_results if item.status is ProviderStatus.VALID
    }
    usable_cases = [case for case in cases if case.id in usable_ids]
    usable_predictions = [
        item.prediction for item in case_results if item.status is ProviderStatus.VALID
    ]
    usable_report = (
        evaluate(
            usable_cases,
            usable_predictions,
            dataset_version=dataset_version,
            split=split,
            split_counts={split: len(usable_cases)},
            baseline_id="model-only-v1-usable-only",
        )
        if usable_cases
        else None
    )
    return ModelExperimentSnapshot(
        experiment_id="model-only-v1",
        created_at=datetime.now(UTC),
        dataset_version=dataset_version,
        dataset_fingerprint=dataset_fingerprint(cases),
        split=split,
        provider=extractor.metadata,
        usable_report=usable_report,
        report=end_to_end_report,
        telemetry=_telemetry(cases, case_results),
        cases=case_results,
    )
