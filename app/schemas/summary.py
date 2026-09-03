"""Public, derived digest models that never contain raw message bodies."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Priority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    UNKNOWN = "unknown"


class Assessment(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNCERTAIN = "uncertain"


class ActionKind(str, Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    NONE = "none"
    UNCERTAIN = "uncertain"


class EmailType(str, Enum):
    ACADEMIC = "academic"
    ADMINISTRATIVE = "administrative"
    SECURITY = "security"
    PERSONAL = "personal"
    RECRUITING = "recruiting"
    EVENT = "event"
    NEWSLETTER = "newsletter"
    PROMOTIONAL = "promotional"
    AUTOMATED = "automated"
    RECEIPT = "receipt"
    DIGEST = "digest"
    UNKNOWN = "unknown"


class Category(str, Enum):
    URGENT = "urgent"
    ACTION_REQUIRED = "action_required"
    REPLY_POSSIBLE = "reply_possible"
    INFORMATIONAL = "informational"
    PROMOTIONAL = "promotional"
    AUTOMATED_NOTIFICATION = "automated_notification"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DateSemanticType(str, Enum):
    DEADLINE = "deadline"
    REGISTRATION_DEADLINE = "registration_deadline"
    EVENT_TIME = "event_time"
    HISTORICAL_DATE = "historical_date"
    PUBLICATION_DATE = "publication_date"
    REFERENCED_DATE = "referenced_date"
    PROMOTION_DATE = "promotion_date"
    UNKNOWN = "unknown"


class EventStatus(str, Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    PAST = "past"
    UNCERTAIN = "uncertain"


class DetectedDate(BaseModel):
    """A date-like phrase and conservative local interpretation."""

    model_config = ConfigDict(extra="forbid")

    text: str
    interpreted_date: date | None = None
    interpreted_at: datetime | None = None
    semantic_type: DateSemanticType
    confidence: Confidence
    context: str


class EmailSummary(BaseModel):
    """Safe public representation of an analyzed email."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    sender_display: str
    sender_domain: str | None = None
    subject: str
    received_at: datetime
    short_summary: str
    priority: Priority
    action_kind: ActionKind
    needs_action: Assessment
    needs_reply: Assessment
    email_type: EmailType
    detected_dates: list[DetectedDate] = Field(default_factory=list)
    contains_event: bool = False
    event_time: datetime | date | None = None
    event_status: EventStatus = EventStatus.UNCERTAIN
    attendance_required: Assessment = Assessment.UNCERTAIN
    registration_available: Assessment = Assessment.UNCERTAIN
    registration_required: Assessment = Assessment.UNCERTAIN
    registration_completed: Assessment = Assessment.UNCERTAIN
    registration_deadline: datetime | date | None = None
    category: Category
    reason: str
    similar_count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_consistency(self) -> "EmailSummary":
        if self.action_kind in {ActionKind.REQUIRED, ActionKind.RECOMMENDED}:
            if self.needs_action is not Assessment.TRUE:
                raise ValueError("required/recommended action must set needs_action=true")
        elif self.action_kind in {ActionKind.OPTIONAL, ActionKind.NONE}:
            if self.needs_action is not Assessment.FALSE:
                raise ValueError("optional/no action must set needs_action=false")
        if self.category is Category.PROMOTIONAL and (
            self.priority is not Priority.LOW
            or self.needs_action is not Assessment.FALSE
        ):
            raise ValueError("promotional category must be low priority with no required action")
        if self.category is Category.URGENT and self.priority is not Priority.URGENT:
            raise ValueError("urgent category requires urgent priority")
        if (
            self.category is Category.ACTION_REQUIRED
            and self.needs_action is not Assessment.TRUE
        ):
            raise ValueError("action_required category requires needs_action=true")
        if self.action_kind is ActionKind.REQUIRED and self.priority is Priority.LOW:
            raise ValueError("required action cannot be low priority")
        if (
            self.email_type is EmailType.PROMOTIONAL
            and self.action_kind is ActionKind.REQUIRED
        ):
            raise ValueError("promotional email cannot be required")
        if self.event_status is EventStatus.UPCOMING and self.priority is Priority.LOW:
            raise ValueError("upcoming event cannot be low priority")
        if (
            self.registration_completed is Assessment.TRUE
            and self.registration_required is Assessment.TRUE
        ):
            raise ValueError("completed registration cannot remain required")
        if (
            self.event_status is EventStatus.UPCOMING
            and self.registration_required is Assessment.TRUE
            and self.registration_completed is not Assessment.TRUE
            and self.action_kind is not ActionKind.REQUIRED
        ):
            raise ValueError("required upcoming registration must be a required action")
        future_deadline = False
        for item in self.detected_dates:
            if item.semantic_type not in {
                DateSemanticType.DEADLINE,
                DateSemanticType.REGISTRATION_DEADLINE,
            }:
                continue
            interpreted = item.interpreted_date or (
                item.interpreted_at.date() if item.interpreted_at else None
            )
            if interpreted is not None and interpreted >= self.received_at.date():
                future_deadline = True
                break
        if future_deadline and self.priority is Priority.LOW:
            raise ValueError("future deadline cannot be low priority")
        if future_deadline and self.action_kind is ActionKind.NONE:
            raise ValueError("future deadline cannot have action_kind=none")
        if self.email_type is EmailType.DIGEST and (
            self.contains_event
            or self.event_time is not None
            or self.event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}
            or any(
                item.semantic_type is DateSemanticType.EVENT_TIME
                for item in self.detected_dates
            )
        ):
            raise ValueError("digest/container cannot inherit embedded event semantics")
        return self


class DigestCounts(BaseModel):
    total_unread: int = 0
    urgent: int = 0
    action_required: int = 0
    possible_reply: int = 0
    informational: int = 0
    low_priority: int = 0
    uncertain: int = 0


class DigestSection(BaseModel):
    title: str
    messages: list[EmailSummary] = Field(default_factory=list)


class UnreadDigest(BaseModel):
    generated_at: datetime
    query: str
    sections: list[DigestSection]
    counts: DigestCounts


class SyncResult(BaseModel):
    """Minimal result for an in-memory, read-only sync."""

    fetched: int
    processed: int
    generated_at: datetime


class HealthResponse(BaseModel):
    status: str = "ok"
    phase: str = "1"
    external_ai_enabled: bool = False
    gmail_scope: str
