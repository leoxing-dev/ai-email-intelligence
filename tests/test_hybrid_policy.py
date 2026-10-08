"""Offline, fixture-free regressions for hybrid-v1-policy-1."""

from __future__ import annotations

from datetime import date

from app.ai.hybrid import combine_predictions
from app.ai.schemas import ProviderStatus
from app.schemas.summary import (
    ActionKind,
    Assessment,
    DateSemanticType,
    EmailType,
    EventStatus,
)
from evaluation.model_schemas import ModelCaseResult
from evaluation.schemas import CasePrediction, EvaluationRoute, PredictedDate


def _prediction(**updates) -> CasePrediction:
    payload = {
        "id": "hybrid_unit_case",
        "email_type": EmailType.ADMINISTRATIVE,
        "action_kind": ActionKind.NONE,
        "needs_reply": Assessment.FALSE,
        "contains_event": False,
        "event_status": EventStatus.UNCERTAIN,
        "registration_available": Assessment.FALSE,
        "registration_required": Assessment.FALSE,
        "registration_completed": Assessment.FALSE,
        "dates": [],
        "route": EvaluationRoute.INFORMATIONAL,
    }
    payload.update(updates)
    return CasePrediction(**payload)


def _model(prediction: CasePrediction, *, confidence: float = 0.95) -> ModelCaseResult:
    return ModelCaseResult(
        case_id=prediction.id,
        status=ProviderStatus.VALID,
        prediction=prediction,
        confidence=confidence,
        latency_ms=1,
        usage={"input_tokens": 1, "output_tokens": 1},
    )


def test_high_risk_agreement_keeps_required_action():
    rules = _prediction(
        action_kind=ActionKind.REQUIRED, route=EvaluationRoute.NEEDS_ACTION
    )
    decision = combine_predictions(rules, _model(rules))

    assert decision.abstained_for_conflict is False
    assert decision.prediction.action_kind is ActionKind.REQUIRED
    assert decision.prediction.route is EvaluationRoute.NEEDS_ACTION


def test_high_risk_disagreement_abstains_without_erasing_rule_semantics():
    rules = _prediction(
        action_kind=ActionKind.REQUIRED, route=EvaluationRoute.NEEDS_ACTION
    )
    model = _prediction(action_kind=ActionKind.NONE)
    decision = combine_predictions(rules, _model(model))

    assert decision.abstained_for_conflict is True
    assert decision.prediction.action_kind is ActionKind.REQUIRED
    assert decision.prediction.route is EvaluationRoute.MANUAL_REVIEW


def test_false_required_action_is_rejected_for_reply_only_message():
    rules = _prediction(needs_reply=Assessment.TRUE, route=EvaluationRoute.NEEDS_REPLY)
    model = _prediction(
        action_kind=ActionKind.REQUIRED,
        needs_reply=Assessment.TRUE,
        route=EvaluationRoute.NEEDS_ACTION,
    )
    decision = combine_predictions(rules, _model(model))

    assert decision.abstained_for_conflict is False
    assert decision.prediction.action_kind is ActionKind.NONE
    assert decision.prediction.needs_reply is Assessment.TRUE
    assert decision.prediction.route is EvaluationRoute.NEEDS_REPLY


def test_model_fills_corroborated_deterministic_required_gap():
    deadline = PredictedDate(
        value=date(2030, 1, 2), semantic_type=DateSemanticType.DEADLINE
    )
    rules = _prediction(
        action_kind=ActionKind.UNCERTAIN, route=EvaluationRoute.MANUAL_REVIEW
    )
    model = _prediction(
        action_kind=ActionKind.REQUIRED,
        dates=[deadline],
        route=EvaluationRoute.NEEDS_ACTION,
    )
    decision = combine_predictions(rules, _model(model))

    assert decision.abstained_for_conflict is False
    assert decision.prediction.action_kind is ActionKind.REQUIRED
    assert decision.prediction.dates == [deadline]
    assert decision.field_sources["action_kind"] == "model"


def test_deterministic_overrides_weak_model_signal():
    rules = _prediction(action_kind=ActionKind.NONE)
    model = _prediction(action_kind=ActionKind.OPTIONAL)
    decision = combine_predictions(rules, _model(model, confidence=0.50))

    assert decision.prediction.action_kind is ActionKind.NONE
    assert decision.field_sources["action_kind"] == "deterministic"


def test_reply_disagreement_retains_definite_deterministic_false():
    rules = _prediction(needs_reply=Assessment.FALSE)
    model = _prediction(needs_reply=Assessment.TRUE, route=EvaluationRoute.NEEDS_REPLY)
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.needs_reply is Assessment.FALSE
    assert decision.prediction.route is EvaluationRoute.INFORMATIONAL


def test_registration_uncertainty_is_not_converted_to_false():
    rules = _prediction(registration_required=Assessment.UNCERTAIN)
    model = _prediction(registration_required=Assessment.FALSE)
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.registration_required is Assessment.UNCERTAIN


def test_deterministic_deadline_is_preserved():
    deadline = PredictedDate(
        value=date(2030, 1, 2), semantic_type=DateSemanticType.DEADLINE
    )
    rules = _prediction(
        action_kind=ActionKind.REQUIRED,
        dates=[deadline],
        route=EvaluationRoute.NEEDS_ACTION,
    )
    model = _prediction(action_kind=ActionKind.REQUIRED, route=EvaluationRoute.NEEDS_ACTION)
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.dates == [deadline]


def test_model_resolves_upcoming_event_gap():
    rules = _prediction(contains_event=True, event_status=EventStatus.UNCERTAIN)
    model = _prediction(
        email_type=EmailType.EVENT,
        contains_event=True,
        event_status=EventStatus.UPCOMING,
        route=EvaluationRoute.UPCOMING_EVENTS,
    )
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.event_status is EventStatus.UPCOMING
    assert decision.prediction.route is EvaluationRoute.UPCOMING_EVENTS


def test_completion_requirement_conflict_abstains():
    rules = _prediction(
        action_kind=ActionKind.REQUIRED,
        registration_required=Assessment.TRUE,
        route=EvaluationRoute.NEEDS_ACTION,
    )
    model = _prediction(registration_completed=Assessment.TRUE)
    decision = combine_predictions(rules, _model(model))

    assert decision.abstained_for_conflict is True
    assert decision.prediction.registration_completed is Assessment.TRUE
    assert decision.prediction.registration_required is Assessment.FALSE
    assert decision.prediction.route is EvaluationRoute.MANUAL_REVIEW


def test_route_normalization_prioritizes_required_action_over_reply():
    rules = _prediction(
        action_kind=ActionKind.REQUIRED,
        needs_reply=Assessment.TRUE,
        route=EvaluationRoute.NEEDS_REPLY,
    )
    model = rules.model_copy(update={"route": EvaluationRoute.NEEDS_ACTION})
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.action_kind is ActionKind.REQUIRED
    assert decision.prediction.needs_reply is Assessment.TRUE
    assert decision.prediction.route is EvaluationRoute.NEEDS_ACTION


def test_digest_type_alone_does_not_force_low_priority():
    rules = _prediction(email_type=EmailType.DIGEST)
    model = _prediction(email_type=EmailType.DIGEST)
    decision = combine_predictions(rules, _model(model))

    assert decision.prediction.route is EvaluationRoute.INFORMATIONAL
