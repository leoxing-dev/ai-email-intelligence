from datetime import datetime

from tests.conftest import encoded, gmail_message

import pytest
from pydantic import ValidationError

from app.schemas.summary import (
    ActionKind,
    Assessment,
    Category,
    Confidence,
    DateSemanticType,
    EmailSummary,
    EmailType,
    Priority,
)
from app.services.email_parser import parse_gmail_message
from app.services.summarizer import LocalSummarizer


def summarize(**kwargs):
    return LocalSummarizer().summarize(parse_gmail_message(gmail_message(**kwargs)))


def test_priority_action_reply_and_explicit_date_detection():
    result = summarize(
        subject="Action required: synthetic registration",
        body=(
            "Please submit the example form by September 8, 2026 at 11:59 PM. "
            "Please reply when complete."
        ),
    )

    assert result.priority is Priority.HIGH
    assert result.needs_action is Assessment.TRUE
    assert result.needs_reply is Assessment.TRUE
    assert result.category is Category.ACTION_REQUIRED
    assert result.detected_dates[0].confidence is Confidence.HIGH
    assert result.detected_dates[0].interpreted_at is not None
    assert result.detected_dates[0].interpreted_at.year == 2026


def test_ambiguous_date_is_not_invented():
    result = summarize(
        subject="Synthetic reminder",
        body="The example item is due Sep 8. Please review it.",
    )

    detected = result.detected_dates[0]
    assert detected.text == "Sep 8"
    assert detected.interpreted_date is None
    assert detected.interpreted_at is None
    assert detected.confidence is Confidence.MEDIUM
    assert detected.context == "Deadline-related date"
    assert detected.semantic_type is DateSemanticType.DEADLINE


def test_date_without_time_does_not_invent_clock_time():
    result = summarize(
        subject="Synthetic dated notice",
        body="The example event is scheduled for 2026-09-12.",
    )

    detected = result.detected_dates[0]
    assert detected.interpreted_date == datetime(2026, 9, 12).date()
    assert detected.interpreted_at is None


def test_urgent_wording_is_explainable():
    result = summarize(
        subject="Urgent synthetic account security notice",
        body="Please verify the example account immediately.",
    )

    assert result.priority is Priority.URGENT
    assert result.category is Category.URGENT
    assert "urgent wording plus meaningful consequence" in result.reason


def test_promotional_and_automated_message_does_not_request_reply():
    result = summarize(
        sender="Synthetic Offers <no-reply@example-shop.test>",
        subject="Synthetic weekly newsletter",
        body="A synthetic promotional update for testing only.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert result.priority is Priority.LOW
    assert result.needs_action is Assessment.FALSE
    assert result.needs_reply is Assessment.FALSE
    assert result.category is Category.PROMOTIONAL


def test_question_without_explicit_request_is_uncertain():
    result = summarize(
        subject="Example discussion",
        body="Is the synthetic outline ready for review?",
    )

    assert result.needs_reply is Assessment.UNCERTAIN
    assert result.category is Category.UNKNOWN


def test_optional_satisfaction_survey_is_not_urgent():
    result = summarize(
        subject="Urgent: tell us what you think",
        body="Please take our optional satisfaction survey today. Don't miss out.",
    )

    assert result.priority is Priority.LOW
    assert result.action_kind is ActionKind.OPTIONAL
    assert result.needs_action is Assessment.FALSE
    assert result.email_type is EmailType.PROMOTIONAL


def test_rideshare_rewards_marketing_has_no_required_action():
    result = summarize(
        sender="Synthetic Rewards <no-reply@rides.example>",
        subject="Earn rewards on every ride",
        body="Claim your reward and explore new ride options for a limited time.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert result.category is Category.PROMOTIONAL
    assert result.priority is Priority.LOW
    assert result.action_kind is ActionKind.OPTIONAL
    assert result.needs_action is Assessment.FALSE


def test_general_safety_advisory_is_high_value_information():
    result = summarize(
        subject="Synthetic campus safety advisory",
        body="This is a general public safety update. No action is required.",
    )

    assert result.priority is Priority.HIGH
    assert result.category is Category.INFORMATIONAL
    assert result.action_kind is ActionKind.NONE
    assert result.needs_action is Assessment.FALSE
    assert result.email_type is EmailType.SECURITY


def test_academic_assignment_due_date_is_required_deadline():
    result = summarize(
        subject="Synthetic course assignment",
        body="Assignment 2 is due September 8, 2026 at 11:59 PM.",
    )

    assert result.priority is Priority.HIGH
    assert result.action_kind is ActionKind.REQUIRED
    assert result.needs_action is Assessment.TRUE
    assert result.email_type is EmailType.ACADEMIC
    assert result.detected_dates[0].semantic_type is DateSemanticType.DEADLINE


def test_professor_response_by_tomorrow_is_reply_and_deadline():
    result = summarize(
        sender="Synthetic Professor <professor@example.edu>",
        subject="Synthetic course question",
        body="Please respond by tomorrow with your selection.",
    )

    assert result.priority is Priority.HIGH
    assert result.needs_reply is Assessment.TRUE
    assert result.action_kind is ActionKind.REQUIRED
    assert result.detected_dates[0].semantic_type is DateSemanticType.DEADLINE


def test_career_fair_is_event_without_automatic_action():
    result = summarize(
        subject="Synthetic career fair announcement",
        body="The career fair takes place September 10, 2026 from 10 AM to 2 PM.",
    )

    assert result.contains_event is True
    assert result.email_type is EmailType.RECRUITING
    assert result.action_kind is ActionKind.NONE
    assert result.needs_action is Assessment.FALSE
    assert result.attendance_required is Assessment.UNCERTAIN
    assert result.detected_dates[0].semantic_type is DateSemanticType.EVENT_TIME


def test_promotional_dates_are_not_deadlines():
    result = summarize(
        subject="Synthetic limited time offer",
        body="The promotion runs September 10, 2026 through September 12, 2026. Shop now.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert result.priority is Priority.LOW
    assert all(
        item.semantic_type is DateSemanticType.PROMOTION_DATE
        for item in result.detected_dates
    )
    assert result.action_kind is ActionKind.OPTIONAL


def test_generic_institutional_newsletter_is_low_not_high_because_of_domain():
    result = summarize(
        sender="Synthetic University News <news@usc.edu>",
        subject="Synthetic institutional newsletter",
        body="This monthly newsletter contains general community updates.",
    )

    assert result.priority is Priority.LOW
    assert result.category is Category.PROMOTIONAL
    assert result.email_type is EmailType.NEWSLETTER
    assert result.needs_action is Assessment.FALSE


def test_account_security_verification_is_urgent():
    result = summarize(
        subject="Urgent synthetic security alert",
        body="Action required: verify your account immediately after unusual sign-in activity.",
    )

    assert result.priority is Priority.URGENT
    assert result.category is Category.URGENT
    assert result.action_kind is ActionKind.REQUIRED
    assert result.email_type is EmailType.SECURITY


def test_boilerplate_is_removed_before_summary_selection():
    result = summarize(
        subject="Synthetic meaningful notice",
        body=(
            "EXTERNAL SENDER\n"
            "View this email in browser.\n"
            "The synthetic program has published a meaningful operational update.\n"
            "Unsubscribe | Manage preferences"
        ),
    )

    assert result.short_summary.startswith("The synthetic program")
    assert "EXTERNAL" not in result.short_summary
    assert "browser" not in result.short_summary


def test_boilerplate_heavy_html_uses_meaningful_content():
    message = gmail_message(subject="Synthetic HTML notice", body="placeholder")
    message["payload"]["mimeType"] = "text/html"
    message["payload"]["body"] = {
        "data": encoded(
            "<div>EXTERNAL SENDER</div>"
            "<div>View this email in browser.</div>"
            "<p>The synthetic program has a meaningful schedule update.</p>"
            "<div>Unsubscribe | Manage preferences</div>"
        )
    }

    result = LocalSummarizer().summarize(parse_gmail_message(message))

    assert result.short_summary == "The synthetic program has a meaningful schedule update."


def test_past_appointment_date_is_historical_not_deadline():
    result = summarize(
        subject="Synthetic appointment record",
        body="The previous appointment was on August 20, 2026.",
    )

    assert result.detected_dates[0].semantic_type is DateSemanticType.HISTORICAL_DATE
    assert result.action_kind is not ActionKind.REQUIRED


def test_contradictory_promotional_priority_is_rejected():
    result = summarize(
        subject="Synthetic offer",
        body="A limited time special offer.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )
    invalid = result.model_dump()
    invalid["priority"] = Priority.HIGH

    with pytest.raises(ValidationError, match="promotional category"):
        EmailSummary.model_validate(invalid)
