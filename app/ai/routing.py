"""Deterministic presentation routing for validated model semantics."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.schemas import ModelRoute, ModelStructuredPrediction
from app.schemas.summary import ActionKind, Assessment, EmailType, EventStatus


@dataclass(frozen=True)
class RouteDecision:
    proposed: ModelRoute
    final: ModelRoute
    reason: str

    @property
    def changed(self) -> bool:
        return self.proposed is not self.final


def normalize_primary_route(prediction: ModelStructuredPrediction) -> RouteDecision:
    """Choose one UI route without changing or invalidating semantic fields.

    Precedence is: explicit abstention; urgent required action; required action;
    reply; upcoming/ongoing event; unresolved manual review; promotional or
    explicitly low-value content; informational fallback.
    """

    proposed = prediction.route
    if prediction.abstain:
        final = ModelRoute.MANUAL_REVIEW
        reason = "model_abstention"
    elif prediction.action_kind is ActionKind.REQUIRED:
        if proposed is ModelRoute.URGENT:
            final = ModelRoute.URGENT
            reason = "urgent_required_action"
        else:
            final = ModelRoute.NEEDS_ACTION
            reason = "required_action"
    elif prediction.needs_reply is Assessment.TRUE:
        final = ModelRoute.NEEDS_REPLY
        reason = "reply_needed"
    elif prediction.event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}:
        final = ModelRoute.UPCOMING_EVENTS
        reason = "upcoming_or_ongoing_event"
    elif proposed is ModelRoute.MANUAL_REVIEW:
        final = ModelRoute.MANUAL_REVIEW
        reason = "unresolved_ambiguity"
    elif (
        prediction.email_type is EmailType.PROMOTIONAL
        or proposed is ModelRoute.LOW_PRIORITY
    ):
        final = ModelRoute.LOW_PRIORITY
        reason = "promotional_or_low_value"
    else:
        final = ModelRoute.INFORMATIONAL
        reason = "informational_fallback"
    return RouteDecision(proposed=proposed, final=final, reason=reason)
