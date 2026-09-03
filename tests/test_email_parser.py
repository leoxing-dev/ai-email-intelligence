from __future__ import annotations

import base64

from tests.conftest import encoded, gmail_message

from app.services.email_parser import html_to_text, parse_gmail_message


def test_plain_text_message_is_parsed(synthetic_message):
    parsed = parse_gmail_message(synthetic_message)

    assert parsed.message_id == "synthetic-message-001"
    assert parsed.sender_display == "Example Instructor"
    assert parsed.sender_address == "instructor@example.edu"
    assert parsed.sender_domain == "example.edu"
    assert "synthetic test content" in parsed.body_text


def test_html_conversion_removes_active_and_tracking_content():
    text = html_to_text(
        "<style>.hidden{}</style><script>steal()</script>"
        "<p>Visible update</p><img src='https://tracker.invalid/pixel'>"
        "<p>Second line</p>"
    )

    assert "Visible update" in text
    assert "Second line" in text
    assert "steal" not in text
    assert "tracker" not in text


def test_nested_hidden_html_is_removed_without_revisiting_detached_children():
    text = html_to_text(
        "<div style='display:none'><span>Hidden preheader text</span></div>"
        "<p>Visible synthetic event information.</p>"
    )

    assert text == "Visible synthetic event information."


def test_nested_multipart_prefers_plain_text_and_ignores_attachment():
    message = gmail_message(body="placeholder")
    message["payload"] = {
        "mimeType": "multipart/mixed",
        "headers": message["payload"]["headers"],
        "body": {},
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "body": {},
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encoded("Preferred local plain text.")},
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": encoded("<p>HTML fallback text.</p>")},
                    },
                ],
            },
            {
                "mimeType": "text/plain",
                "filename": "private-export.txt",
                "body": {
                    "attachmentId": "attachment-not-requested",
                    "data": encoded("Attachment data must not appear."),
                },
            },
        ],
    }

    parsed = parse_gmail_message(message)

    assert parsed.body_text == "Preferred local plain text."
    assert "HTML fallback" not in parsed.body_text
    assert "Attachment data" not in parsed.body_text


def test_html_is_used_when_plain_text_is_unavailable():
    message = gmail_message(body="placeholder")
    message["payload"]["mimeType"] = "text/html"
    message["payload"]["body"] = {
        "data": encoded("<p>Readable <strong>HTML</strong> message.</p>")
    }

    assert parse_gmail_message(message).body_text == "Readable\nHTML\nmessage."


def test_declared_non_utf8_charset_is_decoded_locally():
    message = gmail_message(body="placeholder")
    body_bytes = "Synthetic café notice.".encode("iso-8859-1")
    message["payload"]["headers"].append(
        {"name": "Content-Type", "value": "text/plain; charset=iso-8859-1"}
    )
    message["payload"]["body"] = {
        "data": base64.urlsafe_b64encode(body_bytes).decode("ascii").rstrip("=")
    }

    assert parse_gmail_message(message).body_text == "Synthetic café notice."


def test_quoted_thread_and_signature_are_removed():
    message = gmail_message(
        body=(
            "Newest relevant sentence.\n\n"
            "--\nSynthetic Sender\n"
            "On Sun, Aug 31, 2026 at 9:00 AM Example wrote:\n"
            "> old quoted content"
        )
    )

    assert parse_gmail_message(message).body_text == "Newest relevant sentence."


def test_encoded_headers_and_automated_metadata_are_handled():
    message = gmail_message(
        sender="=?utf-8?q?Automated_Example?= <no-reply@example.org>",
        subject="=?utf-8?q?Synthetic_notification?=",
        extra_headers=[{"name": "Auto-Submitted", "value": "auto-generated"}],
    )

    parsed = parse_gmail_message(message)

    assert parsed.sender_display == "Automated Example"
    assert parsed.subject == "Synthetic notification"
    assert parsed.is_automated is True
