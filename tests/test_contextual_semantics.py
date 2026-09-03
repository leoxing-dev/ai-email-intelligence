"""Synthetic regressions for contextual event, deadline, and action semantics."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from tests.conftest import gmail_message

from app.config import Settings
from app.schemas.summary import (
    ActionKind,
    Assessment,
    DateSemanticType,
    EmailType,
    EventStatus,
    EmailSummary,
    Priority,
)
from app.services.digest_service import DigestService
from app.services.email_parser import parse_gmail_message
from app.services.summarizer import LocalSummarizer


class StubGmailService:
    def __init__(self, messages):
        self.settings = Settings(max_messages=100)
        self._messages = messages

    def fetch_unread(self):
        return self._messages


def summarize(*, subject, body, labels=None):
    return LocalSummarizer().summarize(
        parse_gmail_message(
            gmail_message(subject=subject, body=body, labels=labels)
        )
    )


def summarize_and_route(*, subject, body, labels=None):
    message = gmail_message(subject=subject, body=body, labels=labels)
    digest = DigestService(
        StubGmailService([message]), LocalSummarizer()
    ).unread_digest()
    populated = [section for section in digest.sections if section.messages]
    assert len(populated) == 1
    return populated[0].messages[0], populated[0].title


def test_subject_tomorrow_is_resolved_as_upcoming_event_time():
    summary, section = summarize_and_route(
        subject="Tomorrow! Meet Synthetic Recruiters",
        body="Meet representatives and learn about example opportunities.",
    )

    assert summary.detected_dates[0].interpreted_date == date(2026, 9, 2)
    assert summary.detected_dates[0].semantic_type is DateSemanticType.EVENT_TIME
    assert summary.event_status is EventStatus.UPCOMING
    assert section == "UPCOMING EVENTS"


def test_yearless_numeric_subject_date_is_linked_to_session():
    summary, section = summarize_and_route(
        subject="Synthetic Career in IT Session 9/9",
        body="The session will introduce several example technology roles.",
    )

    assert summary.detected_dates[0].interpreted_date == date(2026, 9, 9)
    assert summary.detected_dates[0].semantic_type is DateSemanticType.EVENT_TIME
    assert summary.event_status is EventStatus.UPCOMING
    assert section == "UPCOMING EVENTS"


def test_newsletter_retains_multiple_contextual_workshop_dates():
    summary, section = summarize_and_route(
        subject="Synthetic workshop newsletter",
        body=(
            "Writing workshop September 4, 2026. "
            "Research workshop September 11, 2026. "
            "Planning workshop September 18, 2026."
        ),
    )

    event_dates = [
        item
        for item in summary.detected_dates
        if item.semantic_type is DateSemanticType.EVENT_TIME
    ]
    assert len(event_dates) == 3
    assert summary.event_status is EventStatus.UPCOMING
    assert section == "UPCOMING EVENTS"


def test_required_rsvp_for_upcoming_event_routes_to_action():
    summary, section = summarize_and_route(
        subject="RSVP required for Synthetic Career Fair September 10",
        body="The fair includes meetings with example organizations.",
    )

    assert summary.event_status is EventStatus.UPCOMING
    assert summary.registration_required is Assessment.TRUE
    assert summary.action_kind is ActionKind.REQUIRED
    assert section == "NEEDS ACTION"


def test_register_here_if_interested_is_available_but_optional():
    summary, section = summarize_and_route(
        subject="Synthetic Open House September 10",
        body="Register here if interested in attending the open house.",
    )

    assert summary.registration_available is Assessment.TRUE
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.OPTIONAL
    assert section == "UPCOMING EVENTS"


def test_already_registered_event_has_no_registration_action():
    summary, section = summarize_and_route(
        subject="You're registered for Synthetic Workshop September 3",
        body="Your registration is confirmed. Event details are available locally.",
    )

    assert summary.registration_completed is Assessment.TRUE
    assert summary.event_status is EventStatus.UPCOMING
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.NONE
    assert section == "UPCOMING EVENTS"


def test_yearless_register_by_date_is_required_but_date_remains_uncertain():
    summary, section = summarize_and_route(
        subject="Synthetic Career Fair September 10",
        body="Register by September 8 to attend the fair.",
    )

    registration_date = next(
        item
        for item in summary.detected_dates
        if item.semantic_type is DateSemanticType.REGISTRATION_DEADLINE
    )
    assert registration_date.text == "September 8"
    assert registration_date.interpreted_date is None
    assert summary.registration_deadline is None
    assert summary.registration_required is Assessment.TRUE
    assert summary.action_kind is ActionKind.REQUIRED
    assert section == "NEEDS ACTION"


def test_registration_closing_date_does_not_imply_universal_requirement():
    summary, section = summarize_and_route(
        subject="Synthetic Career Fair September 10",
        body="Registration closes September 8. Attendance is optional.",
    )

    registration_date = next(
        item
        for item in summary.detected_dates
        if item.semantic_type is DateSemanticType.REGISTRATION_DEADLINE
    )
    assert registration_date.interpreted_date is None
    assert summary.registration_deadline is None
    assert summary.registration_available is Assessment.TRUE
    assert summary.registration_required is not Assessment.TRUE
    assert summary.action_kind is not ActionKind.REQUIRED
    assert section == "UPCOMING EVENTS"


def test_marketing_imperative_never_becomes_required_action():
    summary = summarize(
        subject="Unlock your synthetic discount",
        body="Claim a discount, save, upgrade, and shop now.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert summary.email_type is EmailType.PROMOTIONAL
    assert summary.action_kind is ActionKind.OPTIONAL
    assert summary.priority is Priority.LOW


def test_noncompliance_with_registration_hold_is_required_administration():
    summary, section = summarize_and_route(
        subject="Synthetic Immunization Non-Compliance: Registration Hold",
        body=(
            "Your compliance requirements need to be completed. "
            "A registration hold will be placed if they remain incomplete."
        ),
    )

    assert summary.email_type is EmailType.ADMINISTRATIVE
    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is Priority.HIGH
    assert section == "NEEDS ACTION"


def test_applicable_tax_document_deadline_requires_action():
    summary, section = summarize_and_route(
        subject="Synthetic tax document requirement",
        body="Submit the required tax documentation by December 30, 2026.",
    )

    assert summary.detected_dates[0].semantic_type is DateSemanticType.DEADLINE
    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is not Priority.LOW
    assert section == "NEEDS ACTION"


def test_conditional_document_deadline_preserves_optional_applicability():
    summary = summarize(
        subject="Synthetic optional tax document",
        body="If you want the optional benefit, submit the document by December 30, 2026.",
    )

    assert summary.detected_dates[0].semantic_type is DateSemanticType.DEADLINE
    assert summary.action_kind is ActionKind.OPTIONAL
    assert summary.priority is not Priority.LOW
    assert "conditional" in summary.reason


def test_applicable_deadline_overrides_promotional_bulk_label():
    summary, section = summarize_and_route(
        subject="Synthetic required documentation deadline",
        body="Action required: submit the documentation by September 8, 2026.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is Priority.HIGH
    assert section == "NEEDS ACTION"


def test_upcoming_event_overrides_promotional_bulk_label():
    summary, section = summarize_and_route(
        subject="Synthetic Tech Talk September 12",
        body="Explore new ideas during this example tech talk.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert summary.event_status is EventStatus.UPCOMING
    assert summary.priority is not Priority.LOW
    assert section == "UPCOMING EVENTS"


def test_required_action_invariant_prevents_low_priority():
    summary, section = summarize_and_route(
        subject="Synthetic enrollment requirement",
        body="You must complete the required form to avoid an enrollment problem.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is not Priority.LOW
    assert section == "NEEDS ACTION"


def test_completed_administrative_action_requires_no_new_action():
    summary = summarize(
        subject="Synthetic compliance completion notice",
        body="Your required documentation has been received. No further action is required.",
    )

    assert summary.email_type is EmailType.ADMINISTRATIVE
    assert summary.action_kind is ActionKind.NONE
    assert summary.needs_action is Assessment.FALSE


def test_boilerplate_heavy_event_summary_uses_meaningful_content():
    summary = summarize(
        subject="Synthetic Seminar September 15",
        body=(
            "This email was sent on behalf of Synthetic Communications.\n"
            "To view this email as a web page, click here.\n"
            "CAUTION: This email originated from outside the example organization.\n"
            "The seminar introduces practical synthetic research methods.\n"
            "Manage email preferences"
        ),
    )

    assert summary.short_summary.startswith("The seminar introduces")
    assert "sent on behalf" not in summary.short_summary


def test_model_rejects_low_priority_upcoming_event():
    summary = summarize(
        subject="Synthetic Student Welcome 9/3",
        body="The student welcome provides an example program introduction.",
    )
    invalid = summary.model_dump()
    invalid["priority"] = Priority.LOW

    with pytest.raises(ValidationError, match="upcoming event cannot be low priority"):
        EmailSummary.model_validate(invalid)


def test_model_rejects_low_priority_required_action():
    summary = summarize(
        subject="Synthetic enrollment requirement",
        body="You must complete the required form to avoid an enrollment problem.",
    )
    invalid = summary.model_dump()
    invalid["priority"] = Priority.LOW

    with pytest.raises(ValidationError, match="required action cannot be low priority"):
        EmailSummary.model_validate(invalid)


def test_model_rejects_low_priority_future_deadline():
    summary = summarize(
        subject="Synthetic optional document",
        body="If you want the example benefit, submit the document by December 30, 2026.",
    )
    invalid = summary.model_dump()
    invalid["priority"] = Priority.LOW

    with pytest.raises(ValidationError, match="future deadline cannot be low priority"):
        EmailSummary.model_validate(invalid)
