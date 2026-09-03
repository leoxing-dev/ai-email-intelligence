"""Synthetic tests for early, in-place attachment-data disposal."""

from __future__ import annotations

import json

from tests.conftest import encoded, gmail_message

from app.services.email_parser import (
    parse_gmail_message,
    sanitize_gmail_message_in_place,
)


def _part(mime_type, data, *, filename="", headers=None, attachment_id=None):
    body = {"data": encoded(data), "size": len(data)}
    if attachment_id:
        body["attachmentId"] = attachment_id
    return {
        "mimeType": mime_type,
        "filename": filename,
        "headers": headers or [],
        "body": body,
    }


def _multipart_message(parts):
    message = gmail_message(body="placeholder")
    message["payload"] = {
        "mimeType": "multipart/mixed",
        "headers": message["payload"]["headers"],
        "body": {},
        "parts": parts,
    }
    return message


def test_plain_text_body_remains_available():
    message = gmail_message(body="Synthetic plain body remains available.")

    returned = sanitize_gmail_message_in_place(message)

    assert returned is message
    assert parse_gmail_message(message).body_text == "Synthetic plain body remains available."


def test_html_body_remains_available():
    message = gmail_message(body="placeholder")
    message["payload"]["mimeType"] = "text/html"
    message["payload"]["body"] = {"data": encoded("<p>Synthetic HTML body.</p>")}

    sanitize_gmail_message_in_place(message)

    assert parse_gmail_message(message).body_text == "Synthetic HTML body."


def test_multipart_alternative_body_remains_available():
    message = gmail_message(body="placeholder")
    message["payload"] = {
        "mimeType": "multipart/alternative",
        "headers": message["payload"]["headers"],
        "body": {},
        "parts": [
            _part("text/plain", "Synthetic preferred plain body."),
            _part("text/html", "<p>Synthetic HTML alternative.</p>"),
        ],
    }

    sanitize_gmail_message_in_place(message)

    assert parse_gmail_message(message).body_text == "Synthetic preferred plain body."


def test_attachment_id_and_any_inline_data_are_removed():
    attachment = _part(
        "application/pdf",
        "SYNTHETIC_ATTACHMENT_ID_BYTES",
        filename="synthetic.pdf",
        attachment_id="synthetic-attachment-id",
    )
    message = _multipart_message(
        [_part("text/plain", "Synthetic message body."), attachment]
    )

    sanitize_gmail_message_in_place(message)

    assert attachment["attachment_present"] is True
    assert attachment["body"] == {"size": len("SYNTHETIC_ATTACHMENT_ID_BYTES")}
    assert parse_gmail_message(message).body_text == "Synthetic message body."


def test_attachment_with_inline_body_data_is_stripped_before_parsing():
    marker = "SYNTHETIC_INLINE_ATTACHMENT_BYTES"
    attachment = _part("application/octet-stream", marker, filename="synthetic.bin")
    message = _multipart_message(
        [_part("text/plain", "Synthetic visible body."), attachment]
    )

    sanitize_gmail_message_in_place(message)

    assert "data" not in attachment["body"]
    assert marker not in json.dumps(message)
    assert marker not in parse_gmail_message(message).body_text


def test_nested_multipart_keeps_body_and_discards_attachment():
    marker = "SYNTHETIC_NESTED_ATTACHMENT_BYTES"
    nested_body = {
        "mimeType": "multipart/alternative",
        "headers": [],
        "body": {},
        "parts": [
            _part("text/plain", "Synthetic nested plain body."),
            _part("text/html", "<p>Synthetic nested HTML body.</p>"),
        ],
    }
    attachment = _part("application/pdf", marker, filename="nested.pdf")
    message = _multipart_message([nested_body, attachment])

    sanitize_gmail_message_in_place(message)

    assert parse_gmail_message(message).body_text == "Synthetic nested plain body."
    assert marker not in json.dumps(message)


def test_inline_image_with_file_disposition_is_discarded():
    marker = "SYNTHETIC_INLINE_IMAGE_BYTES"
    image = _part(
        "image/png",
        marker,
        filename="pixel.png",
        headers=[
            {"name": "Content-Disposition", "value": 'inline; filename="pixel.png"'},
            {"name": "Content-ID", "value": "<synthetic-image>"},
        ],
    )
    message = _multipart_message([_part("text/html", "<p>Visible text.</p>"), image])

    sanitize_gmail_message_in_place(message)

    assert image["attachment_present"] is True
    assert "data" not in image["body"]
    assert parse_gmail_message(message).body_text == "Visible text."


def test_sanitizer_never_outputs_or_logs_attachment_bytes(caplog):
    marker = "SYNTHETIC_NEVER_LOG_ATTACHMENT_BYTES"
    attachment = _part(
        "text/plain",
        marker,
        headers=[{"name": "Content-Disposition", "value": "attachment"}],
    )
    message = _multipart_message(
        [_part("text/plain", "Synthetic safe body."), attachment]
    )

    sanitize_gmail_message_in_place(message)

    assert marker not in json.dumps(message)
    assert marker not in caplog.text
    assert marker not in parse_gmail_message(message).body_text


def test_attached_message_descendant_text_is_also_discarded():
    marker = "SYNTHETIC_ATTACHED_MESSAGE_BODY"
    attached_message = {
        "mimeType": "message/rfc822",
        "filename": "forwarded.eml",
        "headers": [],
        "body": {},
        "parts": [_part("text/plain", marker)],
    }
    message = _multipart_message(
        [_part("text/plain", "Synthetic outer body."), attached_message]
    )

    sanitize_gmail_message_in_place(message)

    assert marker not in json.dumps(message)
    assert parse_gmail_message(message).body_text == "Synthetic outer body."

