"""General semantic regressions for the bounded deterministic-rules-v2 pass."""

from __future__ import annotations

from datetime import date

from app.schemas.summary import ActionKind, Assessment, DateSemanticType, EventStatus, Priority
from app.services.email_parser import parse_gmail_message
from app.services.summarizer import LocalSummarizer
from tests.conftest import gmail_message


def _summary(*, subject: str, body: str, labels: list[str] | None = None):
    return LocalSummarizer().summarize(
        parse_gmail_message(gmail_message(subject=subject, body=body, labels=labels))
    )


def test_operational_consequence_with_user_applicability_implies_obligation():
    result = _summary(
        subject="Credential status",
        body=(
            "Your access acknowledgment is still missing. "
            "Without a recorded acknowledgment, portal access will be suspended "
            "after October 6, 2026."
        ),
    )

    assert result.action_kind is ActionKind.REQUIRED
    assert result.priority is Priority.HIGH
    assert any(item.semantic_type is DateSemanticType.DEADLINE for item in result.detected_dates)


def test_marketing_obligation_words_do_not_create_real_obligation():
    result = _summary(
        subject="Mandatory savings alert",
        body="You must order before Friday to unlock bonus points; shopping is optional.",
        labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
    )

    assert result.action_kind is ActionKind.OPTIONAL
    assert result.priority is Priority.LOW


def test_completed_registration_overrides_stale_required_language():
    result = _summary(
        subject="Roster accepted for design forum September 18, 2026",
        body=(
            "Your seat is confirmed. The earlier instructions said registration "
            "is required, but you have no remaining registration step."
        ),
    )

    assert result.registration_completed is Assessment.TRUE
    assert result.registration_required is Assessment.FALSE
    assert result.action_kind is ActionKind.NONE


def test_multiple_dates_receive_clause_local_semantic_roles():
    result = _summary(
        subject="Program schedule",
        body=(
            "The guide was published August 26, 2026. "
            "Send the acknowledgment before September 9, 2026. "
            "The briefing begins September 14, 2026 at 2 PM."
        ),
    )

    roles = {item.interpreted_date: item.semantic_type for item in result.detected_dates}
    assert set(roles.values()) == {
        DateSemanticType.PUBLICATION_DATE,
        DateSemanticType.DEADLINE,
        DateSemanticType.EVENT_TIME,
    }


def test_one_deadline_phrase_does_not_convert_later_event_date():
    result = _summary(
        subject="Research forum",
        body=(
            "Send a response by September 7, 2026; "
            "the forum begins September 16, 2026."
        ),
    )

    assert [item.semantic_type for item in result.detected_dates] == [
        DateSemanticType.DEADLINE,
        DateSemanticType.EVENT_TIME,
    ]


def test_future_announcement_and_historical_recap_are_distinct():
    future = _summary(
        subject="Community lecture",
        body="The lecture begins October 8, 2026 at 4 PM.",
    )
    past = _summary(
        subject="Community lecture archive",
        body="Recordings from the lecture held July 8, 2025 are now available.",
    )

    assert future.event_status is EventStatus.UPCOMING
    assert past.event_status is EventStatus.PAST
    assert past.detected_dates[0].semantic_type is DateSemanticType.HISTORICAL_DATE


def test_optional_benefit_deadline_remains_conditional():
    result = _summary(
        subject="Optional travel benefit",
        body=(
            "If you choose the optional benefit, file a preference before "
            "October 20, 2026."
        ),
    )

    assert result.action_kind is ActionKind.OPTIONAL
    assert result.needs_action is Assessment.FALSE


def test_quoted_obsolete_deadline_does_not_create_current_action():
    result = _summary(
        subject="Re: access form",
        body=(
            "The form was accepted, and nothing else is needed.\n\n"
            "On Tue, Aug 18, 2026 at 9:00 AM Example Office wrote:\n"
            "> Submit the form by August 21, 2026 or access will end."
        ),
    )

    assert result.action_kind is ActionKind.NONE
    assert result.detected_dates == []


def test_event_access_gate_implies_required_registration_without_register_word():
    result = _summary(
        subject="Laboratory tour October 12, 2026",
        body="Only visitors whose names are on the roster can enter the tour.",
    )

    assert result.event_status is EventStatus.UPCOMING
    assert result.registration_available is Assessment.TRUE
    assert result.registration_required is Assessment.TRUE
    assert result.action_kind is ActionKind.REQUIRED


def test_hour_only_relative_time_does_not_inherit_received_minutes():
    message = gmail_message(
        subject="Briefing today at 7 PM",
        body="The briefing covers the revised operating plan.",
    )
    date_header = next(
        item for item in message["payload"]["headers"] if item["name"] == "Date"
    )
    date_header["value"] = "Tue, 01 Sep 2026 10:37:00 -0700"

    result = LocalSummarizer().summarize(parse_gmail_message(message))

    assert result.detected_dates[0].interpreted_at is not None
    assert result.detected_dates[0].interpreted_at.minute == 0


def test_this_and_next_weekday_have_distinct_calendar_meanings():
    current = _summary(
        subject="Office hours this Friday",
        body="Office hours begin at noon.",
    )
    following = _summary(
        subject="Office hours next Friday",
        body="Office hours begin at noon.",
    )

    assert current.detected_dates[0].interpreted_date == date(2026, 9, 4)
    assert following.detected_dates[0].interpreted_date == date(2026, 9, 11)
