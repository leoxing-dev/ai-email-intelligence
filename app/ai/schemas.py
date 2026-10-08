"""Strict provider-neutral schemas for synthetic model evaluation."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.schemas.summary import ActionKind, Assessment, DateSemanticType, EmailType, EventStatus
class ProviderStatus(str, Enum):
    VALID = "valid"
    ABSTAINED = "abstained"
    MALFORMED = "malformed"
    FAILED = "failed"


class ProviderOutcome(str, Enum):
    """Detailed execution outcome; ProviderStatus remains the coarse compatibility view."""

    PROVIDER_FAILURE = "provider_failure"
    PROVIDER_REFUSAL = "provider_refusal"
    STRUCTURED_OUTPUT_FAILURE = "structured_output_failure"
    DOMAIN_VALIDATION_FAILURE = "domain_validation_failure"
    NORMALIZATION_FAILURE = "normalization_failure"
    MODEL_ABSTENTION = "model_abstention"
    VALID_PREDICTION = "valid_prediction"


class ValidationStage(str, Enum):
    STRUCTURED_OUTPUT = "structured_output"
    DOMAIN = "domain"
    NORMALIZATION = "normalization"


class ValidationIssue(BaseModel):
    """Privacy-safe validation diagnostic retained in model snapshots."""

    model_config = ConfigDict(extra="forbid")

    stage: ValidationStage
    field: str
    received_type: str
    received_value: str | int | float | bool | None = None
    expected: str
    validation_error: str


class ModelRoute(str, Enum):
    URGENT = "urgent"
    NEEDS_ACTION = "needs_action"
    NEEDS_REPLY = "needs_reply"
    UPCOMING_EVENTS = "upcoming_events"
    INFORMATIONAL = "informational"
    LOW_PRIORITY = "low_priority"
    MANUAL_REVIEW = "manual_review"


class SyntheticEmailRecord(BaseModel):
    """Explicit trust-boundary type accepted by external model adapters."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["synthetic-email-benchmark-v2"]
    case_id: str
    subject: str = Field(repr=False)
    body: str = Field(repr=False)
    received_at: datetime
    timezone: str
    sender: str = Field(repr=False)
    body_format: Literal["plain", "html"]
    labels: list[str]


class ModelDate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: date | datetime | None
    semantic_type: DateSemanticType
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(max_length=240)


EvidenceText = Annotated[str, Field(max_length=240)]


class ModelStructuredPrediction(BaseModel):
    """Canonical structural contract used by OpenAI JSON Schema and runtime parsing."""

    model_config = ConfigDict(extra="forbid", strict=True)

    email_type: EmailType
    action_kind: ActionKind
    needs_reply: Assessment
    contains_event: bool
    event_status: EventStatus
    registration_available: Assessment
    registration_required: Assessment
    registration_completed: Assessment
    dates: list[ModelDate] = Field(max_length=10)
    route: ModelRoute
    confidence: float = Field(ge=0, le=1)
    abstain: bool
    rationale: str = Field(max_length=500)
    evidence: list[EvidenceText] = Field(max_length=8)


def validate_prediction_domain(
    prediction: ModelStructuredPrediction,
) -> list[ValidationIssue]:
    """Validate cross-field semantics that JSON Schema cannot express safely."""

    issues: list[ValidationIssue] = []
    if prediction.registration_completed is Assessment.TRUE and (
        prediction.registration_required is Assessment.TRUE
    ):
        issues.append(
            ValidationIssue(
                stage=ValidationStage.DOMAIN,
                field="registration_completed",
                received_type="string",
                received_value=prediction.registration_completed.value,
                expected="completed registration cannot remain required",
                validation_error="completed_registration_still_required",
            )
        )
    return issues


_SAFE_DIAGNOSTIC_ROOTS = {
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
    "confidence",
    "abstain",
}


def validation_issues_from_error(
    error: ValidationError,
    *,
    stage: ValidationStage,
) -> list[ValidationIssue]:
    """Convert Pydantic errors to bounded diagnostics without retaining free text."""

    issues: list[ValidationIssue] = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "$"
        received: Any = item.get("input")
        root = location.split(".", 1)[0]
        safe_value: str | int | float | bool | None = None
        if root in _SAFE_DIAGNOSTIC_ROOTS and isinstance(
            received, (str, int, float, bool)
        ):
            rendered = str(received)
            safe_value = received if not isinstance(received, str) else rendered[:80]
        issues.append(
            ValidationIssue(
                stage=stage,
                field=location,
                received_type=type(received).__name__,
                received_value=safe_value,
                expected=str(item.get("msg") or item.get("type") or "valid value")[:240],
                validation_error=str(item.get("type") or "validation_error")[:120],
            )
        )
    return issues


def coarse_status_for_outcome(outcome: ProviderOutcome) -> ProviderStatus:
    if outcome is ProviderOutcome.VALID_PREDICTION:
        return ProviderStatus.VALID
    if outcome in {ProviderOutcome.PROVIDER_REFUSAL, ProviderOutcome.MODEL_ABSTENTION}:
        return ProviderStatus.ABSTAINED
    if outcome is ProviderOutcome.PROVIDER_FAILURE:
        return ProviderStatus.FAILED
    return ProviderStatus.MALFORMED


def infer_outcome(status: ProviderStatus, error_code: str | None) -> ProviderOutcome:
    """Load legacy results while new executions always set an explicit outcome."""

    if status is ProviderStatus.VALID:
        return ProviderOutcome.VALID_PREDICTION
    if error_code == "model_refusal":
        return ProviderOutcome.PROVIDER_REFUSAL
    if status is ProviderStatus.ABSTAINED:
        return ProviderOutcome.MODEL_ABSTENTION
    if error_code == "domain_validation":
        return ProviderOutcome.DOMAIN_VALIDATION_FAILURE
    if error_code == "normalization_failure":
        return ProviderOutcome.NORMALIZATION_FAILURE
    if status is ProviderStatus.MALFORMED:
        return ProviderOutcome.STRUCTURED_OUTPUT_FAILURE
    return ProviderOutcome.PROVIDER_FAILURE


class ProviderMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    model_version: str
    reasoning_effort: str | None
    service_tier: str | None
    prompt_version: str


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    reported: bool = False


class ProviderResult(BaseModel):
    """One provider call; no request body, key, or raw response is retained."""

    model_config = ConfigDict(extra="forbid")

    status: ProviderStatus
    outcome: ProviderOutcome | None = None
    prediction: ModelStructuredPrediction | None = None
    metadata: ProviderMetadata
    latency_ms: float = Field(ge=0)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    validation_errors: list[ValidationIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "ProviderResult":
        if self.outcome is None:
            self.outcome = infer_outcome(self.status, self.error_code)
        if self.status is not coarse_status_for_outcome(self.outcome):
            raise ValueError("provider status and detailed outcome disagree")
        if self.status is ProviderStatus.VALID and self.prediction is None:
            raise ValueError("valid result requires a prediction")
        if self.status is not ProviderStatus.VALID and self.prediction is not None:
            raise ValueError("non-valid result cannot retain a prediction")
        return self
