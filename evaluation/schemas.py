"""Versioned evaluation-only schemas; prediction data stays separate from labels."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.summary import (
    ActionKind,
    Assessment,
    DateSemanticType,
    EmailType,
    EventStatus,
)


class EvaluationRoute(str, Enum):
    URGENT = "urgent"
    NEEDS_ACTION = "needs_action"
    NEEDS_REPLY = "needs_reply"
    UPCOMING_EVENTS = "upcoming_events"
    INFORMATIONAL = "informational"
    LOW_PRIORITY = "low_priority"
    MANUAL_REVIEW = "manual_review"


class EvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str
    received_at: datetime
    sender: str = "Synthetic Sender <sender@benchmark.example>"
    body_format: Literal["plain", "html"] = "plain"
    mime_structure: Literal["simple", "multipart_alternative", "nested_multipart"] = (
        "simple"
    )
    encoding_mode: Literal["valid", "invalid_base64url", "invalid_utf8"] = "valid"
    labels: list[str] = Field(default_factory=lambda: ["INBOX", "UNREAD"])
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("received_at")
    @classmethod
    def require_aware_received_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluation received_at must include a timezone")
        return value


class ExpectedDate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: date | datetime
    semantic_type: DateSemanticType


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_type: EmailType
    action_kind: ActionKind
    needs_reply: Assessment
    contains_event: bool
    event_status: EventStatus
    registration_available: Assessment
    registration_required: Assessment
    registration_completed: Assessment
    dates: list[ExpectedDate] = Field(default_factory=list)
    expected_route: EvaluationRoute


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    input: EvaluationInput
    ground_truth: GroundTruth
    tags: list[str] = Field(min_length=1)
    family_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,63}$")

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        normalized = sorted({tag.strip().lower() for tag in value if tag.strip()})
        if not normalized:
            raise ValueError("each evaluation case needs at least one tag")
        return normalized


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    default_timezone: str
    split_order: list[str]
    split_files: dict[str, str]
    assignment_policy: str


class BinaryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    recall: float | None
    f1: float | None


class DateMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_count: int
    predicted_count: int
    date_only_match_count: int
    extraction_precision: float | None
    extraction_recall: float | None
    exact_normalized_match_count: int
    exact_normalized_match_rate: float | None
    timed_expected_count: int
    time_tolerance_match_count: int
    time_tolerance_accuracy: float | None
    tolerance_minutes: int


class AbstentionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    accepted: int
    abstained: int
    coverage: float | None
    accepted_route_errors: int
    error_rate_among_accepted: float | None


class ProtectedMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    false_required_action_count: int
    false_required_action_rate: float | None
    required_action_false_negative_count: int
    upcoming_event_false_negative_count: int
    deadline_false_negative_count: int


class TagMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: int
    route_correct: int
    route_accuracy: float | None
    binary_metrics: dict[str, BinaryMetrics]
    date_metrics: DateMetrics


class PredictedDate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: date | datetime | None
    semantic_type: DateSemanticType


class CasePrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email_type: EmailType
    action_kind: ActionKind
    needs_reply: Assessment
    contains_event: bool
    event_status: EventStatus
    registration_available: Assessment
    registration_required: Assessment
    registration_completed: Assessment
    dates: list[PredictedDate]
    route: EvaluationRoute
    model_proposed_route: EvaluationRoute | None = None


class CaseFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tags: list[str]
    expected: dict[str, object]
    predicted: dict[str, object]


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_id: str
    dataset_version: str
    dataset_fingerprint: str
    split: str
    case_count: int
    split_counts: dict[str, int]
    binary_metrics: dict[str, BinaryMetrics]
    route_labels: list[EvaluationRoute]
    route_confusion: dict[str, dict[str, int]]
    route_accuracy: float | None
    model_proposed_route_confusion: dict[str, dict[str, int]] | None = None
    model_proposed_route_accuracy: float | None = None
    normalized_route_confusion: dict[str, dict[str, int]] | None = None
    normalized_route_accuracy: float | None = None
    date_metrics: DateMetrics
    abstention: AbstentionMetrics
    protected_metrics: ProtectedMetrics
    by_tag: dict[str, TagMetrics]
    predictions: list[CasePrediction]
    failures: list[CaseFailure]
