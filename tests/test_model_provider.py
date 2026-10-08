"""Offline tests for provider abstraction, validation, telemetry, and hybrid policy."""

from __future__ import annotations

from datetime import date, datetime
import json

import httpx
import pytest
from pydantic import SecretStr

from app.ai.config import ModelSettings
from app.ai.hybrid import combine_predictions
from app.ai.providers.fake import FakeModelExtractor
from app.ai.providers.openai import OpenAIModelExtractor
from app.ai.schemas import (
    ModelStructuredPrediction,
    ProviderOutcome,
    ProviderResult,
    ProviderStatus,
    SyntheticEmailRecord,
    TokenUsage,
)
from app.schemas.summary import ActionKind, Assessment, EmailType, EventStatus
from evaluation.model_pipeline import provider_result_to_case, run_model_experiment
from evaluation.model_schemas import ModelCaseResult
from evaluation.schemas import (
    CasePrediction,
    EvaluationCase,
    EvaluationInput,
    EvaluationRoute,
    GroundTruth,
)


def _structured(**updates):
    payload = {
        "email_type": "administrative",
        "action_kind": "required",
        "needs_reply": "false",
        "contains_event": False,
        "event_status": "uncertain",
        "registration_available": "false",
        "registration_required": "false",
        "registration_completed": "false",
        "dates": [],
        "route": "needs_action",
        "confidence": 0.88,
        "abstain": False,
        "rationale": "An applicable operational step is stated.",
        "evidence": ["The record requests completion."],
    }
    payload.update(updates)
    return payload


def _record() -> SyntheticEmailRecord:
    return SyntheticEmailRecord(
        source="synthetic-email-benchmark-v2",
        case_id="provider_unit_case",
        subject="Synthetic record notice",
        body="Complete the example record before October 4, 2026.",
        received_at="2026-09-01T10:00:00-07:00",
        timezone="America/Los_Angeles",
        sender="Synthetic Office <office@provider.example>",
        body_format="plain",
        labels=["INBOX", "UNREAD"],
    )


def _case() -> EvaluationCase:
    return EvaluationCase(
        id="provider_unit_case",
        family_id="provider_unit_family",
        input=EvaluationInput(
            subject="Synthetic record notice",
            body="Complete the example record before October 4, 2026.",
            received_at="2026-09-01T10:00:00-07:00",
        ),
        ground_truth=GroundTruth(
            email_type=EmailType.ADMINISTRATIVE,
            action_kind=ActionKind.REQUIRED,
            needs_reply=Assessment.FALSE,
            contains_event=False,
            event_status=EventStatus.UNCERTAIN,
            registration_available=Assessment.FALSE,
            registration_required=Assessment.FALSE,
            registration_completed=Assessment.FALSE,
            expected_route=EvaluationRoute.NEEDS_ACTION,
        ),
        tags=["provider_test"],
    )


def _prediction(*, required: bool, route: EvaluationRoute) -> CasePrediction:
    return CasePrediction(
        id="provider_unit_case",
        email_type=EmailType.ADMINISTRATIVE,
        action_kind=ActionKind.REQUIRED if required else ActionKind.NONE,
        needs_reply=Assessment.FALSE,
        contains_event=False,
        event_status=EventStatus.UNCERTAIN,
        registration_available=Assessment.FALSE,
        registration_required=Assessment.FALSE,
        registration_completed=Assessment.FALSE,
        dates=[],
        route=route,
    )


def test_fake_provider_validates_and_records_latency_without_body_retention():
    provider = FakeModelExtractor([_structured()], latency_ms=12.5)
    result = provider.extract(_record())
    stored = provider_result_to_case("provider_unit_case", result)

    assert result.status is ProviderStatus.VALID
    assert stored.latency_ms == 12.5
    assert stored.usage.input_tokens == 100
    assert provider.seen_case_ids == ["provider_unit_case"]
    assert "Complete the example" not in stored.model_dump_json()


@pytest.mark.parametrize(
    ("response", "status", "outcome", "code"),
    [
        (
            {"unexpected": True},
            ProviderStatus.MALFORMED,
            ProviderOutcome.STRUCTURED_OUTPUT_FAILURE,
            "structured_output_validation",
        ),
        (
            TimeoutError(),
            ProviderStatus.FAILED,
            ProviderOutcome.PROVIDER_FAILURE,
            "timeout",
        ),
        (
            _structured(
                action_kind="uncertain",
                route="manual_review",
                confidence=0.25,
                abstain=True,
            ),
            ProviderStatus.ABSTAINED,
            ProviderOutcome.MODEL_ABSTENTION,
            "model_abstention",
        ),
    ],
)
def test_fake_provider_fails_closed(response, status, outcome, code):
    result = FakeModelExtractor([response]).extract(_record())

    assert result.status is status
    assert result.outcome is outcome
    assert result.prediction is None
    assert result.error_code == code


def test_canonical_structured_schema_matches_runtime_field_contract():
    schema = ModelStructuredPrediction.model_json_schema()
    properties = schema["properties"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(properties)
    assert properties["evidence"]["items"]["maxLength"] == 240
    assert properties["dates"]["type"] == "array"
    assert properties["dates"]["maxItems"] == 10
    date_value = schema["$defs"]["ModelDate"]["properties"]["value"]["anyOf"]
    assert {item.get("format") or item.get("type") for item in date_value} == {
        "date",
        "date-time",
        "null",
    }
    assert schema["$defs"]["Assessment"]["enum"] == [
        "true",
        "false",
        "uncertain",
    ]


def test_api_shaped_structured_output_normalizes_null_dates_and_multiple_values():
    payload = _structured(
        email_type="event",
        action_kind="optional",
        contains_event=True,
        event_status="upcoming",
        registration_available="true",
        dates=[
            {
                "value": "2026-09-18",
                "semantic_type": "registration_deadline",
                "confidence": 0.91,
                "evidence": "Registration closes on the stated date.",
            },
            {
                "value": "2026-09-20T14:30:00-07:00",
                "semantic_type": "event_time",
                "confidence": 0.93,
                "evidence": "The event time is explicitly stated.",
            },
            {
                "value": None,
                "semantic_type": "unknown",
                "confidence": 0.25,
                "evidence": "A third date cannot be normalized safely.",
            },
        ],
        route="upcoming_events",
    )

    result = FakeModelExtractor([payload]).extract(_record())
    normalized = provider_result_to_case("provider_unit_case", result)

    assert result.outcome is ProviderOutcome.VALID_PREDICTION
    assert normalized.outcome is ProviderOutcome.VALID_PREDICTION
    assert normalized.prediction.dates[0].value == date(2026, 9, 18)
    assert normalized.prediction.dates[1].value == datetime.fromisoformat(
        "2026-09-20T14:30:00-07:00"
    )
    assert normalized.prediction.dates[2].value is None


def test_nullable_date_is_required_even_when_its_value_may_be_null():
    payload = _structured(
        dates=[
            {
                "semantic_type": "unknown",
                "confidence": 0.2,
                "evidence": "No normalized date is available.",
            }
        ]
    )

    result = FakeModelExtractor([payload]).extract(_record())

    assert result.outcome is ProviderOutcome.STRUCTURED_OUTPUT_FAILURE
    assert result.validation_errors[0].field == "dates.0.value"
    assert result.usage.reported is True


@pytest.mark.parametrize(
    ("updates", "error"),
    [
        (
            {
                "action_kind": "none",
                "registration_required": "true",
                "registration_completed": "true",
                "route": "informational",
            },
            "completed_registration_still_required",
        ),
    ],
)
def test_structurally_valid_cross_field_conflicts_are_domain_failures(updates, error):
    result = FakeModelExtractor([_structured(**updates)]).extract(_record())

    assert result.status is ProviderStatus.MALFORMED
    assert result.outcome is ProviderOutcome.DOMAIN_VALIDATION_FAILURE
    assert any(item.validation_error == error for item in result.validation_errors)
    assert result.usage == TokenUsage(
        input_tokens=100, output_tokens=40, reported=True
    )
    assert result.estimated_cost_usd == pytest.approx(0.00068)


@pytest.mark.parametrize(
    ("updates", "expected_route"),
    [
        (
            {
                "action_kind": "required",
                "needs_reply": "true",
                "route": "needs_reply",
            },
            EvaluationRoute.NEEDS_ACTION,
        ),
        (
            {
                "action_kind": "required",
                "contains_event": True,
                "event_status": "upcoming",
                "route": "upcoming_events",
            },
            EvaluationRoute.NEEDS_ACTION,
        ),
        (
            {
                "action_kind": "required",
                "dates": [
                    {
                        "value": "2026-09-08",
                        "semantic_type": "deadline",
                        "confidence": 0.9,
                        "evidence": "A deadline is stated.",
                    }
                ],
                "route": "informational",
            },
            EvaluationRoute.NEEDS_ACTION,
        ),
        (
            {
                "action_kind": "none",
                "needs_reply": "true",
                "route": "informational",
            },
            EvaluationRoute.NEEDS_REPLY,
        ),
        (
            {
                "action_kind": "none",
                "contains_event": True,
                "event_status": "upcoming",
                "route": "informational",
            },
            EvaluationRoute.UPCOMING_EVENTS,
        ),
        (
            {
                "action_kind": "uncertain",
                "needs_reply": "true",
                "contains_event": True,
                "event_status": "upcoming",
                "route": "manual_review",
            },
            EvaluationRoute.NEEDS_REPLY,
        ),
        (
            {"action_kind": "required", "route": "urgent"},
            EvaluationRoute.URGENT,
        ),
        (
            {"action_kind": "uncertain", "route": "manual_review"},
            EvaluationRoute.MANUAL_REVIEW,
        ),
        (
            {
                "email_type": "promotional",
                "action_kind": "none",
                "route": "informational",
            },
            EvaluationRoute.LOW_PRIORITY,
        ),
        (
            {"action_kind": "none", "route": "needs_action"},
            EvaluationRoute.INFORMATIONAL,
        ),
    ],
)
def test_valid_multi_signal_predictions_use_deterministic_route_precedence(
    updates, expected_route
):
    result = FakeModelExtractor([_structured(**updates)]).extract(_record())
    normalized = provider_result_to_case("provider_unit_case", result)

    assert result.outcome is ProviderOutcome.VALID_PREDICTION
    assert normalized.outcome is ProviderOutcome.VALID_PREDICTION
    assert normalized.prediction.route is expected_route
    assert normalized.prediction.model_proposed_route is EvaluationRoute(
        updates["route"]
    )
    if updates.get("needs_reply") == "true":
        assert normalized.prediction.needs_reply is Assessment.TRUE


def test_completed_registration_can_coexist_with_an_unrelated_required_action():
    result = FakeModelExtractor(
        [
            _structured(
                action_kind="required",
                registration_required="false",
                registration_completed="true",
                route="needs_reply",
            )
        ]
    ).extract(_record())
    normalized = provider_result_to_case("provider_unit_case", result)

    assert result.outcome is ProviderOutcome.VALID_PREDICTION
    assert normalized.prediction.registration_completed is Assessment.TRUE
    assert normalized.prediction.route is EvaluationRoute.NEEDS_ACTION


def test_evaluator_separates_model_proposed_and_normalized_route_accuracy():
    snapshot = run_model_experiment(
        [_case()],
        extractor=FakeModelExtractor(
            [_structured(needs_reply="true", route="needs_reply")]
        ),
        timezone_name="America/Los_Angeles",
        dataset_version="synthetic-email-benchmark-v2",
        split="v2_dev",
        split_counts={"v2_dev": 1},
    )

    assert snapshot.telemetry.usable_prediction_count == 1
    assert snapshot.report.model_proposed_route_accuracy == 0
    assert snapshot.report.normalized_route_accuracy == 1
    assert snapshot.report.route_accuracy == 1
    assert snapshot.report.model_proposed_route_confusion["needs_action"]["needs_reply"] == 1
    assert snapshot.report.normalized_route_confusion["needs_action"]["needs_action"] == 1


def test_invalid_enum_is_a_structured_output_failure_with_safe_diagnostics():
    result = FakeModelExtractor([_structured(event_status="scheduled")]).extract(
        _record()
    )

    assert result.outcome is ProviderOutcome.STRUCTURED_OUTPUT_FAILURE
    issue = result.validation_errors[0]
    assert issue.field == "event_status"
    assert issue.received_value == "scheduled"
    assert issue.received_type == "str"


def test_normalization_failure_is_distinct_and_preserves_billable_usage():
    prediction = ModelStructuredPrediction.model_validate_json(json.dumps(_structured()))
    object.__setattr__(prediction, "route", "not_an_evaluation_route")
    provider = FakeModelExtractor([])
    result = ProviderResult(
        status=ProviderStatus.VALID,
        outcome=ProviderOutcome.VALID_PREDICTION,
        prediction=prediction,
        metadata=provider.metadata,
        latency_ms=11,
        usage=TokenUsage(input_tokens=120, output_tokens=30, reported=True),
        estimated_cost_usd=0.0006,
    )

    normalized = provider_result_to_case("provider_unit_case", result)

    assert normalized.status is ProviderStatus.MALFORMED
    assert normalized.outcome is ProviderOutcome.NORMALIZATION_FAILURE
    assert normalized.error_code == "normalization_failure"
    assert normalized.usage.reported is True
    assert normalized.estimated_cost_usd == pytest.approx(0.0006)


def test_schema_invalid_billable_result_contributes_to_usage_cost_and_taxonomy():
    snapshot = run_model_experiment(
        [_case()],
        extractor=FakeModelExtractor([{"unexpected": True}]),
        timezone_name="America/Los_Angeles",
        dataset_version="synthetic-email-benchmark-v2",
        split="v2_dev",
        split_counts={"v2_dev": 1},
    )

    telemetry = snapshot.telemetry
    assert telemetry.billable_attempt_count == 1
    assert telemetry.total_input_tokens == 100
    assert telemetry.total_output_tokens == 40
    assert telemetry.total_tokens == 140
    assert telemetry.estimated_total_cost_usd == pytest.approx(0.00068)
    assert telemetry.estimated_cost_per_1000_emails_usd == pytest.approx(0.68)
    assert telemetry.outcome_counts["structured_output_failure"] == 1
    assert telemetry.request_success_rate == 1
    assert telemetry.structured_output_success_rate == 0
    assert telemetry.usable_prediction_rate == 0
    assert snapshot.usable_report is None


def test_semantic_quality_is_separate_from_end_to_end_quality():
    first = _case()
    second = _case().model_copy(update={"id": "provider_unit_case_two"})
    snapshot = run_model_experiment(
        [first, second],
        extractor=FakeModelExtractor([_structured(), {"unexpected": True}]),
        timezone_name="America/Los_Angeles",
        dataset_version="synthetic-email-benchmark-v2",
        split="v2_dev",
        split_counts={"v2_dev": 2},
    )

    assert snapshot.report.case_count == 2
    assert snapshot.report.binary_metrics["required_action"].recall == 0.5
    assert snapshot.usable_report is not None
    assert snapshot.usable_report.case_count == 1
    assert snapshot.usable_report.binary_metrics["required_action"].recall == 1
    assert snapshot.telemetry.usable_prediction_rate == 0.5


def test_model_experiment_tracks_quality_failures_and_cost_without_fixture_text():
    snapshot = run_model_experiment(
        [_case()],
        extractor=FakeModelExtractor([_structured()]),
        timezone_name="America/Los_Angeles",
        dataset_version="synthetic-email-benchmark-v2",
        split="v2_dev",
        split_counts={"v2_dev": 1},
    )

    assert snapshot.report.binary_metrics["required_action"].f1 == 1
    assert snapshot.telemetry.valid_count == 1
    assert snapshot.telemetry.estimated_cost_per_1000_emails_usd == pytest.approx(0.68)
    serialized = snapshot.model_dump_json()
    assert "Complete the example record" not in serialized
    assert '"body"' not in serialized


def test_hybrid_abstains_on_high_risk_disagreement():
    rules = _prediction(required=True, route=EvaluationRoute.NEEDS_ACTION)
    model_result = ModelCaseResult(
        case_id=rules.id,
        status=ProviderStatus.VALID,
        prediction=_prediction(required=False, route=EvaluationRoute.INFORMATIONAL),
        confidence=0.95,
        latency_ms=20,
        usage={"input_tokens": 10, "output_tokens": 5},
    )

    decision = combine_predictions(rules, model_result)

    assert decision.abstained_for_conflict is True
    # Preserve the bounded deterministic semantic signal while abstaining from
    # a primary presentation route; this protects required-action recall.
    assert decision.prediction.action_kind is ActionKind.REQUIRED
    assert decision.prediction.route is EvaluationRoute.MANUAL_REVIEW


def test_hybrid_uses_rules_when_provider_fails():
    rules = _prediction(required=True, route=EvaluationRoute.NEEDS_ACTION)
    failed = ModelCaseResult(
        case_id=rules.id,
        status=ProviderStatus.FAILED,
        prediction=_prediction(required=False, route=EvaluationRoute.MANUAL_REVIEW),
        confidence=0,
        latency_ms=20,
        usage={"input_tokens": 0, "output_tokens": 0},
        error_code="timeout",
    )

    assert combine_predictions(rules, failed).prediction == rules


def test_openai_adapter_uses_structured_responses_without_storage_or_fast_tier():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": "gpt-5.6-terra",
                "service_tier": "default",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": json.dumps(_structured())}
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 120,
                    "input_tokens_details": {"cached_tokens": 20},
                    "output_tokens": 50,
                    "output_tokens_details": {"reasoning_tokens": 10},
                },
            },
        )

    settings = ModelSettings(
        provider="openai",
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        service_tier="default",
        api_key=SecretStr("unit-test-placeholder"),
    )
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = OpenAIModelExtractor(settings, client=client).extract(_record())

    assert result.status is ProviderStatus.VALID
    assert result.outcome is ProviderOutcome.VALID_PREDICTION
    assert observed["store"] is False
    assert observed["service_tier"] == "default"
    assert observed["reasoning"] == {"effort": "medium"}
    assert observed["text"]["format"]["type"] == "json_schema"
    assert observed["text"]["format"]["strict"] is True
    assert result.usage.reasoning_tokens == 10
    assert result.usage.reported is True
    assert result.estimated_cost_usd == pytest.approx(0.000804)


@pytest.mark.parametrize(
    ("content", "outcome", "error_code"),
    [
        (
            [{"type": "output_text", "text": json.dumps({"unexpected": True})}],
            ProviderOutcome.STRUCTURED_OUTPUT_FAILURE,
            "structured_output_validation",
        ),
        (
            [{"type": "refusal", "refusal": "Cannot classify this fixture."}],
            ProviderOutcome.PROVIDER_REFUSAL,
            "model_refusal",
        ),
    ],
)
def test_completed_openai_failures_retain_usage_and_precise_taxonomy(
    content, outcome, error_code
):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": "gpt-5.6-terra",
                "service_tier": "default",
                "output": [{"type": "message", "content": content}],
                "usage": {
                    "input_tokens": 90,
                    "input_tokens_details": {"cached_tokens": 10},
                    "output_tokens": 20,
                    "output_tokens_details": {"reasoning_tokens": 4},
                },
            },
        )

    settings = ModelSettings(
        provider="openai",
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        service_tier="default",
        api_key=SecretStr("unit-test-placeholder"),
    )
    result = OpenAIModelExtractor(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler))
    ).extract(_record())

    assert result.outcome is outcome
    assert result.error_code == error_code
    assert result.usage == TokenUsage(
        input_tokens=90,
        cached_input_tokens=10,
        output_tokens=20,
        reasoning_tokens=4,
        reported=True,
    )
    assert result.estimated_cost_usd == pytest.approx(0.000402)


def test_provider_disabled_mode_requires_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GMAIL_ASSISTANT_MODEL_PROVIDER", raising=False)

    settings = ModelSettings()

    assert settings.provider == "disabled"
    assert settings.api_key is None
