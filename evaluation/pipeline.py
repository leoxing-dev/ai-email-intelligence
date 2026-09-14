"""Run synthetic cases through the same parser, summarizer, and router as Gmail."""

from __future__ import annotations

import base64
from email.utils import format_datetime
from typing import Any

from app.schemas.summary import ActionKind, Assessment, EmailType, EventStatus
from app.services.digest_service import SECTION_TITLES, section_title_for_summary
from app.services.email_parser import EmailParseError, parse_gmail_message
from app.services.summarizer import LocalSummarizer
from evaluation.schemas import (
    CasePrediction,
    EvaluationCase,
    EvaluationRoute,
    PredictedDate,
)


_SECTION_ROUTES = {
    SECTION_TITLES[0]: EvaluationRoute.URGENT,
    SECTION_TITLES[1]: EvaluationRoute.NEEDS_ACTION,
    SECTION_TITLES[2]: EvaluationRoute.NEEDS_REPLY,
    SECTION_TITLES[3]: EvaluationRoute.UPCOMING_EVENTS,
    SECTION_TITLES[4]: EvaluationRoute.INFORMATIONAL,
    SECTION_TITLES[5]: EvaluationRoute.INFORMATIONAL,
    SECTION_TITLES[6]: EvaluationRoute.LOW_PRIORITY,
    SECTION_TITLES[7]: EvaluationRoute.MANUAL_REVIEW,
}


def _encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _body_data(case: EvaluationCase) -> str:
    if case.input.encoding_mode == "invalid_base64url":
        return "%%%not-base64url%%%"
    if case.input.encoding_mode == "invalid_utf8":
        return base64.urlsafe_b64encode(b"\xff\xfe\xfa").decode("ascii").rstrip("=")
    return _encoded(case.input.body)


def case_to_gmail_payload(case: EvaluationCase) -> dict[str, Any]:
    """Adapt one synthetic record to a Gmail-shaped payload entirely in memory."""

    headers = [
        {"name": "From", "value": case.input.sender},
        {"name": "Subject", "value": case.input.subject},
        {"name": "Date", "value": format_datetime(case.input.received_at)},
    ]
    headers.extend(
        {"name": name, "value": value}
        for name, value in sorted(case.input.headers.items())
    )
    mime_type = "text/html" if case.input.body_format == "html" else "text/plain"
    leaf = {"mimeType": mime_type, "body": {"data": _body_data(case)}}
    if case.input.mime_structure == "multipart_alternative":
        payload_body = {
            "mimeType": "multipart/alternative",
            "headers": headers,
            "body": {},
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _body_data(case)}},
                {
                    "mimeType": "text/html",
                    "body": {"data": _encoded(f"<p>{case.input.body}</p>")},
                },
            ],
        }
    elif case.input.mime_structure == "nested_multipart":
        payload_body = {
            "mimeType": "multipart/mixed",
            "headers": headers,
            "body": {},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {},
                    "parts": [leaf],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "synthetic-not-fetched.pdf",
                    "body": {"attachmentId": "synthetic-attachment"},
                },
            ],
        }
    else:
        payload_body = {
            "mimeType": mime_type,
            "headers": headers,
            "body": {"data": _body_data(case)},
        }
    return {
        "id": case.id,
        "threadId": f"evaluation-{case.id}",
        "internalDate": str(int(case.input.received_at.timestamp() * 1000)),
        "labelIds": case.input.labels,
        "payload": payload_body,
    }


def predict_case(
    case: EvaluationCase, *, summarizer: LocalSummarizer
) -> CasePrediction:
    """Evaluate through production MIME parsing, classification, and routing."""

    try:
        parsed = parse_gmail_message(case_to_gmail_payload(case))
    except EmailParseError:
        # Production skips an unparseable message with a privacy-safe warning.
        # The benchmark records that safe non-classification as abstention.
        return CasePrediction(
            id=case.id,
            email_type=EmailType.UNKNOWN,
            action_kind=ActionKind.UNCERTAIN,
            needs_reply=Assessment.UNCERTAIN,
            contains_event=False,
            event_status=EventStatus.UNCERTAIN,
            registration_available=Assessment.UNCERTAIN,
            registration_required=Assessment.UNCERTAIN,
            registration_completed=Assessment.UNCERTAIN,
            dates=[],
            route=EvaluationRoute.MANUAL_REVIEW,
        )
    summary = summarizer.summarize(parsed)
    route = _SECTION_ROUTES[section_title_for_summary(summary)]
    return CasePrediction(
        id=case.id,
        email_type=summary.email_type,
        action_kind=summary.action_kind,
        needs_reply=summary.needs_reply,
        contains_event=summary.contains_event,
        event_status=summary.event_status,
        registration_available=summary.registration_available,
        registration_required=summary.registration_required,
        registration_completed=summary.registration_completed,
        dates=[
            PredictedDate(
                value=item.interpreted_at or item.interpreted_date,
                semantic_type=item.semantic_type,
            )
            for item in summary.detected_dates
        ],
        route=route,
    )


def predict_cases(
    cases: list[EvaluationCase], *, timezone_name: str
) -> list[CasePrediction]:
    summarizer = LocalSummarizer(timezone_name)
    return [predict_case(case, summarizer=summarizer) for case in cases]
