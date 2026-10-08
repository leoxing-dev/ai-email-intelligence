"""Conservative, versioned fusion of deterministic and model predictions."""

from __future__ import annotations

from dataclasses import dataclass

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


HYBRID_POLICY_VERSION = "hybrid-v1-policy-1"
MODEL_FILL_THRESHOLD = 0.80
_LOW_VALUE_TYPES = {EmailType.NEWSLETTER, EmailType.PROMOTIONAL}
_HIGH_RISK_DATES = {
    DateSemanticType.DEADLINE,
    DateSemanticType.REGISTRATION_DEADLINE,
}


@dataclass(frozen=True)
class HybridDecision:
    prediction: CasePrediction
    confidence: float
    abstained_for_conflict: bool
    field_sources: dict[str, str]
    disagreements: tuple[str, ...]
    policy_decisions: tuple[str, ...]


def _has_deadline(prediction: CasePrediction) -> bool:
    return any(item.semantic_type in _HIGH_RISK_DATES for item in prediction.dates)


def _disagreements(
    rules: CasePrediction, model: CasePrediction
) -> tuple[str, ...]:
    fields = (
        "email_type",
        "action_kind",
        "needs_reply",
        "contains_event",
        "event_status",
        "registration_available",
        "registration_required",
        "registration_completed",
        "dates",
        "route",
    )
    return tuple(name for name in fields if getattr(rules, name) != getattr(model, name))


def _base_sources(rules: CasePrediction, model: CasePrediction) -> dict[str, str]:
    return {
        name: "agreement" if getattr(rules, name) == getattr(model, name) else "deterministic"
        for name in (
            "email_type",
            "action_kind",
            "needs_reply",
            "contains_event",
            "event_status",
            "registration_available",
            "registration_required",
            "registration_completed",
            "dates",
        )
    }


def _model_dates_are_corroborated(
    dates: list[PredictedDate],
    *,
    action_kind: ActionKind,
    registration_required: Assessment,
    contains_event: bool,
    event_status: EventStatus,
) -> bool:
    for item in dates:
        if item.semantic_type in _HIGH_RISK_DATES and (
            action_kind is ActionKind.REQUIRED
            or registration_required is Assessment.TRUE
        ):
            return True
        if item.semantic_type is DateSemanticType.EVENT_TIME and (
            contains_event
            and event_status
            in {EventStatus.UPCOMING, EventStatus.ONGOING, EventStatus.PAST}
        ):
            return True
    return False


def combine_predictions(
    rules: CasePrediction,
    model_result: ModelCaseResult,
) -> HybridDecision:
    """Fuse independent semantic fields with risk-aware deterministic precedence.

    Definite deterministic high-risk findings are retained because they are
    evidence-bounded. A model-only high-risk positive requires corroborating
    semantics; otherwise the primary route abstains. Model output may resolve
    deterministic uncertainty in lower-risk fields, but never turns uncertain
    registration state into false merely for convenience.
    """

    model = model_result.prediction
    if model_result.status is not ProviderStatus.VALID:
        return HybridDecision(
            prediction=rules,
            confidence=0.80,
            abstained_for_conflict=False,
            field_sources={name: "deterministic" for name in _base_sources(rules, model)},
            disagreements=_disagreements(rules, model),
            policy_decisions=("provider_unusable_use_deterministic",),
        )

    model_confident = model_result.confidence >= MODEL_FILL_THRESHOLD
    sources = _base_sources(rules, model)
    decisions: list[str] = []
    abstain = False

    email_type = rules.email_type
    if (
        rules.email_type is EmailType.UNKNOWN
        and model.email_type is not EmailType.UNKNOWN
        and model_confident
    ):
        email_type = model.email_type
        sources["email_type"] = "model"
        decisions.append("model_fills_unknown_email_type")

    rules_required = rules.action_kind is ActionKind.REQUIRED
    model_required = model.action_kind is ActionKind.REQUIRED
    action_kind = rules.action_kind
    if rules_required and not model_required:
        if rules.registration_required is Assessment.TRUE or _has_deadline(rules):
            decisions.append("retain_corroborated_deterministic_required_action")
        else:
            abstain = True
            decisions.append("review_uncorroborated_required_action_disagreement")
    elif model_required and not rules_required:
        reply_only_signal = (
            rules.needs_reply is Assessment.TRUE
            and model.needs_reply is Assessment.TRUE
            and rules.registration_required is not Assessment.TRUE
            and not _has_deadline(model)
        )
        model_required_corroborated = (
            model_confident
            and rules.action_kind is ActionKind.UNCERTAIN
            and (
                model.registration_required is Assessment.TRUE
                or _has_deadline(model)
            )
        )
        if reply_only_signal:
            action_kind = ActionKind.NONE
            sources["action_kind"] = "policy"
            decisions.append("reject_reply_only_required_action")
        elif model_required_corroborated:
            action_kind = ActionKind.REQUIRED
            sources["action_kind"] = "model"
            decisions.append("model_fills_corroborated_required_action_gap")
        else:
            abstain = True
            decisions.append("review_uncorroborated_model_required_action")
    elif (
        rules.action_kind is ActionKind.UNCERTAIN
        and model.action_kind is not ActionKind.UNCERTAIN
        and model_confident
    ):
        action_kind = model.action_kind
        sources["action_kind"] = "model"
        decisions.append("model_resolves_nonrequired_action_uncertainty")

    needs_reply = rules.needs_reply
    if rules.needs_reply is Assessment.UNCERTAIN and model_confident:
        needs_reply = model.needs_reply
        sources["needs_reply"] = "model"
        decisions.append("model_resolves_reply_uncertainty")
    elif rules.needs_reply is not model.needs_reply:
        decisions.append("retain_definite_deterministic_reply_signal")

    contains_event = rules.contains_event
    if (
        not rules.contains_event
        and model.contains_event
        and model.event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}
        and model_confident
    ):
        contains_event = True
        sources["contains_event"] = "model"
        decisions.append("model_fills_coherent_event_gap")

    event_status = rules.event_status
    if (
        rules.event_status is EventStatus.UNCERTAIN
        and model.event_status is not EventStatus.UNCERTAIN
        and contains_event
        and model_confident
    ):
        event_status = model.event_status
        sources["event_status"] = "model"
        decisions.append("model_resolves_event_status_uncertainty")

    registration_available = rules.registration_available
    if (
        rules.registration_available is Assessment.UNCERTAIN
        and model.registration_available is Assessment.TRUE
        and contains_event
        and model_confident
    ):
        registration_available = Assessment.TRUE
        sources["registration_available"] = "model"
        decisions.append("model_fills_positive_registration_availability")

    completion = rules.registration_completed
    if completion is not Assessment.TRUE and model.registration_completed is Assessment.TRUE:
        if model_confident:
            completion = Assessment.TRUE
            sources["registration_completed"] = "model"
            decisions.append("accept_explicit_model_registration_completion")

    registration_required = rules.registration_required
    if completion is Assessment.TRUE:
        if registration_required is Assessment.TRUE:
            abstain = True
            decisions.append("review_completion_requirement_conflict")
        registration_required = Assessment.FALSE
        sources["registration_required"] = "policy"
        decisions.append("completion_clears_registration_requirement")
    elif (
        rules.registration_required is Assessment.UNCERTAIN
        and model.registration_required is Assessment.TRUE
        and model_confident
        and action_kind is ActionKind.REQUIRED
        and (
            registration_available is Assessment.TRUE or _has_deadline(model)
        )
    ):
        registration_required = Assessment.TRUE
        sources["registration_required"] = "model"
        decisions.append("model_fills_corroborated_registration_requirement")
    elif rules.registration_required is Assessment.UNCERTAIN:
        decisions.append("preserve_registration_requirement_uncertainty")

    dates = rules.dates
    if (
        not dates
        and model.dates
        and model_confident
        and _model_dates_are_corroborated(
            model.dates,
            action_kind=action_kind,
            registration_required=registration_required,
            contains_event=contains_event,
            event_status=event_status,
        )
    ):
        dates = model.dates
        sources["dates"] = "model"
        decisions.append("model_fills_corroborated_date_gap")

    if abstain:
        route = EvaluationRoute.MANUAL_REVIEW
        decisions.append("manual_review_for_high_risk_conflict")
    elif action_kind is ActionKind.REQUIRED:
        route = (
            EvaluationRoute.URGENT
            if rules.route is EvaluationRoute.URGENT
            else EvaluationRoute.NEEDS_ACTION
        )
        decisions.append("route_required_action")
    elif needs_reply is Assessment.TRUE:
        route = EvaluationRoute.NEEDS_REPLY
        decisions.append("route_reply")
    elif event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}:
        route = EvaluationRoute.UPCOMING_EVENTS
        decisions.append("route_upcoming_event")
    else:
        low_value_agreement = (
            rules.email_type is model.email_type
            and rules.email_type in _LOW_VALUE_TYPES
        ) or (
            rules.route is EvaluationRoute.LOW_PRIORITY
            and model.route is EvaluationRoute.LOW_PRIORITY
        )
        if low_value_agreement:
            route = EvaluationRoute.LOW_PRIORITY
            decisions.append("route_agreed_low_value")
        elif (
            rules.route is EvaluationRoute.MANUAL_REVIEW
            and model.route
            in {EvaluationRoute.INFORMATIONAL, EvaluationRoute.LOW_PRIORITY}
            and model_confident
        ):
            route = model.route
            decisions.append("model_resolves_low_risk_route_review")
        elif (
            rules.route is EvaluationRoute.LOW_PRIORITY
            and model.route is EvaluationRoute.INFORMATIONAL
            and model_confident
        ):
            route = EvaluationRoute.INFORMATIONAL
            decisions.append("model_resolves_low_priority_disagreement")
        else:
            route = EvaluationRoute.INFORMATIONAL
            decisions.append("route_informational_fallback")

    sources["route"] = "policy"
    prediction = rules.model_copy(
        update={
            "email_type": email_type,
            "action_kind": action_kind,
            "needs_reply": needs_reply,
            "contains_event": contains_event,
            "event_status": event_status,
            "registration_available": registration_available,
            "registration_required": registration_required,
            "registration_completed": completion,
            "dates": dates,
            "route": route,
            "model_proposed_route": model.route,
        }
    )
    confidence = (
        min(0.49, model_result.confidence)
        if abstain
        else (
            min(1.0, (0.90 + model_result.confidence) / 2)
            if rules.route is model.route
            else min(0.89, model_result.confidence)
        )
    )
    return HybridDecision(
        prediction=prediction,
        confidence=confidence,
        abstained_for_conflict=abstain,
        field_sources=sources,
        disagreements=_disagreements(rules, model),
        policy_decisions=tuple(dict.fromkeys(decisions)),
    )
