"""Synthetic regressions for the final targeted Phase 1 correctness pass."""

from __future__ import annotations

from datetime import date, timedelta
import warnings

import pytest
from dateutil.parser import UnknownTimezoneWarning
from pydantic import ValidationError

from tests.conftest import encoded, gmail_message

from app.config import DEFAULT_TIMEZONE, Settings
from app.schemas.summary import (
    ActionKind,
    Assessment,
    Category,
    EmailSummary,
    EmailType,
    EventStatus,
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


def _message(*, received_header=None, **kwargs):
    message = gmail_message(**kwargs)
    if received_header:
        date_header = next(
            header
            for header in message["payload"]["headers"]
            if header["name"].lower() == "date"
        )
        date_header["value"] = received_header
    return message


def _summarize(*, timezone_name=DEFAULT_TIMEZONE, received_header=None, **kwargs):
    return LocalSummarizer(timezone_name).summarize(
        parse_gmail_message(_message(received_header=received_header, **kwargs))
    )


def _summarize_and_route(**kwargs):
    message = _message(**kwargs)
    summary = LocalSummarizer(DEFAULT_TIMEZONE).summarize(parse_gmail_message(message))
    digest = DigestService(
        StubGmailService([message]), LocalSummarizer(DEFAULT_TIMEZONE)
    ).unread_digest()
    populated = [section for section in digest.sections if section.messages]
    assert len(populated) == 1
    return summary, populated[0].title


def test_tomorrow_uses_pacific_date_across_utc_midnight():
    summary = _summarize(
        received_header="Thu, 03 Sep 2026 01:30:00 +0000",
        subject="Synthetic Event Tomorrow at 1 PM",
        body="The event presents a synthetic topic.",
    )

    detected = summary.detected_dates[0]
    assert detected.interpreted_date == date(2026, 9, 3)
    assert detected.interpreted_at is not None
    assert detected.interpreted_at.hour == 13
    assert detected.interpreted_at.utcoffset() == timedelta(hours=-7)


def test_timezone_configuration_defaults_and_can_be_overridden(monkeypatch):
    monkeypatch.delenv("GMAIL_ASSISTANT_DEFAULT_TIMEZONE", raising=False)
    assert Settings(_env_file=None).default_timezone == "America/Los_Angeles"

    monkeypatch.setenv("GMAIL_ASSISTANT_DEFAULT_TIMEZONE", "America/New_York")
    assert Settings(_env_file=None).default_timezone == "America/New_York"


def test_unknown_timezone_is_rejected_without_host_fallback():
    with pytest.raises(ValidationError, match="recognized IANA timezone"):
        Settings(default_timezone="Invalid/Synthetic_Zone", _env_file=None)


def test_today_uses_configured_local_date():
    summary = _summarize(
        received_header="Thu, 03 Sep 2026 23:30:00 +0000",
        subject="Synthetic Workshop Today at 6 PM",
        body="The workshop provides visible synthetic content.",
    )

    assert summary.detected_dates[0].interpreted_date == date(2026, 9, 3)
    assert summary.event_status is EventStatus.ONGOING


@pytest.mark.parametrize(
    ("label", "expected_offset"),
    [("PDT", -7), ("PST", -8)],
)
def test_explicit_pacific_timezone_is_preserved(label, expected_offset):
    summary = _summarize(
        subject=f"Synthetic Seminar September 10, 2026 at 1 PM {label}",
        body="The seminar contains synthetic information.",
    )

    interpreted = summary.detected_dates[0].interpreted_at
    assert interpreted is not None
    assert interpreted.utcoffset() == timedelta(hours=expected_offset)


def test_yearless_event_time_with_pdt_is_inferred_without_timezone_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        summary = _summarize(
            subject="Synthetic Workshop September 10 at 1 PM PDT",
            body="The workshop contains synthetic information.",
        )

    interpreted = summary.detected_dates[0].interpreted_at
    assert interpreted is not None
    assert interpreted.date() == date(2026, 9, 10)
    assert interpreted.utcoffset() == timedelta(hours=-7)
    assert not any(
        isinstance(item.message, UnknownTimezoneWarning) for item in caught
    )


def test_relative_date_uses_daylight_saving_offset_for_result_date():
    summary = _summarize(
        received_header="Sun, 08 Mar 2026 07:30:00 +0000",
        subject="Synthetic Event Tomorrow at 1 PM",
        body="The event contains synthetic information.",
    )

    interpreted = summary.detected_dates[0].interpreted_at
    assert interpreted is not None
    assert interpreted.date() == date(2026, 3, 8)
    assert interpreted.utcoffset() == timedelta(hours=-7)


@pytest.mark.parametrize(
    ("subject", "body"),
    [
        ("Unlock your synthetic reward", "Get free membership and earn points."),
        ("Claim a synthetic discount", "Save on rides and shop now."),
    ],
)
def test_marketing_calls_to_action_are_optional(subject, body):
    summary = _summarize(
        sender="Synthetic Offers <no-reply@offers.example>",
        subject=subject,
        body=body,
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert summary.email_type is EmailType.PROMOTIONAL
    assert summary.action_kind is ActionKind.OPTIONAL
    assert summary.needs_action is Assessment.FALSE
    assert summary.priority is Priority.LOW


def test_promotional_model_cannot_be_required():
    summary = _summarize(
        sender="Synthetic Offers <no-reply@offers.example>",
        subject="Unlock your synthetic reward",
        body="Claim a reward and earn points.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )
    invalid = summary.model_dump()
    invalid.update(
        action_kind=ActionKind.REQUIRED,
        needs_action=Assessment.TRUE,
        priority=Priority.HIGH,
        category=Category.ACTION_REQUIRED,
    )

    with pytest.raises(ValidationError, match="promotional email cannot be required"):
        EmailSummary.model_validate(invalid)


def test_general_safety_advice_is_recommended_informational():
    summary, section = _summarize_and_route(
        subject="Synthetic public safety advisory",
        body="Wear a helmet, lock your scooter, stay alert, and take precautions.",
    )

    assert summary.email_type is EmailType.SECURITY
    assert summary.action_kind is ActionKind.RECOMMENDED
    assert summary.category is Category.INFORMATIONAL
    assert summary.priority is Priority.HIGH
    assert section == "IMPORTANT INFORMATIONAL"

    message = _message(
        subject="Synthetic public safety advisory",
        body="Wear a helmet, lock your scooter, stay alert, and take precautions.",
    )
    digest = DigestService(
        StubGmailService([message]), LocalSummarizer(DEFAULT_TIMEZONE)
    ).unread_digest()
    assert digest.counts.action_required == 0


def test_mandatory_emergency_order_is_required_and_urgent():
    summary, section = _summarize_and_route(
        subject="Urgent synthetic emergency order",
        body="Mandatory evacuation: you must evacuate immediately.",
    )

    assert summary.email_type is EmailType.SECURITY
    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is Priority.URGENT
    assert section == "URGENT / TIME-SENSITIVE"


@pytest.mark.parametrize(
    ("subject", "body"),
    [
        (
            "You're registered for Synthetic Workshop September 10, 2026",
            "The workshop includes a synthetic demonstration.",
        ),
        (
            "Synthetic Workshop September 10, 2026",
            "Your registration was successful. The workshop includes a demonstration.",
        ),
    ],
)
def test_registration_completion_is_detected_in_subject_or_body(subject, body):
    summary = _summarize(subject=subject, body=body)

    assert summary.registration_completed is Assessment.TRUE
    assert summary.registration_required is Assessment.FALSE
    assert summary.action_kind is ActionKind.NONE


def test_upcoming_registered_event_routes_without_registration_action():
    summary, section = _summarize_and_route(
        subject="Registration successful for Synthetic Workshop September 10, 2026",
        body="You're registered. The workshop includes a synthetic demonstration.",
    )

    assert summary.event_status is EventStatus.UPCOMING
    assert summary.registration_completed is Assessment.TRUE
    assert summary.action_kind is ActionKind.NONE
    assert section == "UPCOMING EVENTS"


def test_security_digest_embedded_event_is_not_container_event():
    summary, section = _summarize_and_route(
        subject="Synthetic Security Quarantine Digest",
        body=(
            "Held item summary: Career Fair Tomorrow at 1 PM. RSVP required.\n"
            "This digest lists quarantined items for local review."
        ),
    )

    assert summary.email_type is EmailType.DIGEST
    assert summary.contains_event is False
    assert summary.event_status is EventStatus.UNCERTAIN
    assert section == "OTHER INFORMATIONAL / NEWSLETTERS"


def test_digest_embedded_timestamps_are_not_container_dates():
    summary = _summarize(
        subject="Synthetic Daily Notification Digest",
        body=(
            "Held item received September 3, 2026 at 8 AM.\n"
            "Second item received September 3, 2026 at 9 AM.\n"
            "Embedded webinar September 10, 2026 at 1 PM."
        ),
    )

    assert summary.email_type is EmailType.DIGEST
    assert summary.detected_dates == []
    assert summary.contains_event is False


def test_conditional_document_deadline_is_not_universally_required():
    summary = _summarize(
        subject="Synthetic benefit document",
        body=(
            "If you plan to claim the optional benefit, submit the tax document "
            "by December 30, 2026."
        ),
    )

    assert summary.action_kind is ActionKind.OPTIONAL
    assert summary.detected_dates
    assert "conditional" in summary.reason


def test_unconditional_document_deadline_is_required():
    summary = _summarize(
        subject="Synthetic required tax document",
        body="You must submit the required tax document by December 30, 2026.",
    )

    assert summary.action_kind is ActionKind.REQUIRED
    assert summary.priority is Priority.HIGH


def test_html_style_hidden_preheader_and_entities_do_not_replace_visible_summary():
    message = _message(subject="Synthetic Seminar September 10, 2026", body="placeholder")
    message["payload"]["mimeType"] = "text/html"
    message["payload"]["body"] = {
        "data": encoded(
            "<style>table.button table td { color: red; padding: 10px; }</style>"
            "<script>trackSynthetic()</script>"
            "<div style='display:none'>Hidden synthetic preheader&nbsp;&zwnj;</div>"
            "<p>The seminar explains research &amp; planning methods.</p>"
        )
    }

    summary = LocalSummarizer(DEFAULT_TIMEZONE).summarize(parse_gmail_message(message))

    assert summary.short_summary == "The seminar explains research & planning methods."
    assert "table.button" not in summary.short_summary
    assert "preheader" not in summary.short_summary
