"""Synthetic regressions for event value and registration routing."""

from __future__ import annotations

from tests.conftest import gmail_message

from app.config import Settings
from app.schemas.summary import (
    ActionKind,
    Assessment,
    DateSemanticType,
    EmailType,
    EventStatus,
    Priority,
)
from app.services.digest_service import DigestService
from app.services.summarizer import LocalSummarizer


class StubGmailService:
    def __init__(self, messages):
        self.settings = Settings(max_messages=20)
        self._messages = messages

    def fetch_unread(self):
        return self._messages


def _digest_for(message):
    return DigestService(StubGmailService([message]), LocalSummarizer()).unread_digest()


def _summary_and_section(message):
    digest = _digest_for(message)
    populated = [section for section in digest.sections if section.messages]
    assert len(populated) == 1
    return populated[0].messages[0], populated[0].title


def test_newsletter_career_fair_with_required_rsvp_needs_action():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic opportunities newsletter",
            body=(
                "RSVP required by September 8, 2026. "
                "The career fair takes place September 10, 2026."
            ),
        )
    )

    assert summary.email_type is EmailType.NEWSLETTER
    assert summary.event_status is EventStatus.UPCOMING
    assert summary.registration_required is Assessment.TRUE
    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is Priority.HIGH
    assert section == "NEEDS ACTION"


def test_newsletter_career_fair_with_optional_rsvp_is_upcoming_event():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic opportunities newsletter",
            body=(
                "Register here if you'd like to attend. "
                "The career fair takes place September 10, 2026."
            ),
        )
    )

    assert summary.registration_available is Assessment.TRUE
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.OPTIONAL
    assert section == "UPCOMING EVENTS"


def test_newsletter_with_three_upcoming_workshops_preserves_all_dates():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic workshops newsletter",
            body=(
                "Workshop one takes place September 10, 2026. "
                "Workshop two takes place September 17, 2026. "
                "Workshop three takes place September 24, 2026."
            ),
        )
    )

    event_dates = [
        item for item in summary.detected_dates if item.semantic_type is DateSemanticType.EVENT_TIME
    ]
    assert len(event_dates) == 3
    assert summary.event_status is EventStatus.UPCOMING
    assert section == "UPCOMING EVENTS"


def test_promotional_email_with_expired_event_is_low_priority():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic promotional event recap",
            body="Our promotional event was held August 20, 2026. Explore current offers.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        )
    )

    assert summary.event_status is EventStatus.PAST
    assert summary.priority is Priority.LOW
    assert section == "LOW PRIORITY / PROMOTIONAL"


def test_academic_bulk_deadline_overrides_promotional_format():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic graduation application newsletter",
            body="Submit your graduation application by September 8, 2026.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        )
    )

    assert summary.email_type is EmailType.ADMINISTRATIVE
    assert summary.priority is Priority.HIGH
    assert summary.action_kind is ActionKind.REQUIRED
    assert section == "NEEDS ACTION"


def test_registration_successful_requires_no_further_action():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic workshop confirmation",
            body=(
                "Registration successful. "
                "The workshop takes place September 10, 2026."
            ),
        )
    )

    assert summary.event_status is EventStatus.UPCOMING
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.NONE
    assert section == "UPCOMING EVENTS"


def test_no_registration_required_event_has_no_action():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic public workshop",
            body=(
                "No registration required. "
                "The workshop takes place September 10, 2026."
            ),
        )
    )

    assert summary.registration_available is Assessment.FALSE
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.NONE
    assert section == "UPCOMING EVENTS"


def test_marketing_newsletter_with_useful_event_is_retained():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic community newsletter",
            body=(
                "Explore our special offer. "
                "A graduate workshop takes place September 17, 2026."
            ),
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        )
    )

    assert summary.email_type is EmailType.NEWSLETTER
    assert summary.event_status is EventStatus.UPCOMING
    assert summary.priority is not Priority.LOW
    assert section == "UPCOMING EVENTS"


def test_generic_promotional_newsletter_remains_low_priority():
    summary, section = _summary_and_section(
        gmail_message(
            subject="Synthetic rewards newsletter",
            body="Explore our rewards and claim a special offer.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        )
    )

    assert summary.event_status is EventStatus.UNCERTAIN
    assert summary.priority is Priority.LOW
    assert section == "LOW PRIORITY / PROMOTIONAL"


def test_registration_deadline_is_distinct_from_event_date():
    summary, _ = _summary_and_section(
        gmail_message(
            subject="Synthetic career newsletter",
            body=(
                "RSVP required by September 8, 2026. "
                "The career fair takes place September 10, 2026."
            ),
        )
    )

    semantics = {item.semantic_type for item in summary.detected_dates}
    assert DateSemanticType.REGISTRATION_DEADLINE in semantics
    assert DateSemanticType.EVENT_TIME in semantics
    assert str(summary.registration_deadline) == "2026-09-08"
    assert str(summary.event_time) == "2026-09-10"
