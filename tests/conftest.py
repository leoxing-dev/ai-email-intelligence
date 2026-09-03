"""Synthetic Gmail fixtures only—never use exported or live mailbox data here."""

from __future__ import annotations

import base64
from typing import Any

import pytest


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def gmail_message(
    *,
    message_id: str = "synthetic-message-001",
    sender: str = "Example Instructor <instructor@example.edu>",
    subject: str = "Synthetic course update",
    body: str = "This is synthetic test content with no personal information.",
    labels: list[str] | None = None,
    extra_headers: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    headers = [
        {"name": "From", "value": sender},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": "Mon, 01 Sep 2026 10:00:00 -0700"},
    ]
    headers.extend(extra_headers or [])
    return {
        "id": message_id,
        "threadId": "synthetic-thread-001",
        "internalDate": "1788282000000",
        "labelIds": labels or ["INBOX", "UNREAD"],
        "payload": {
            "mimeType": "text/plain",
            "headers": headers,
            "body": {"data": encoded(body)},
        },
    }


@pytest.fixture
def synthetic_message() -> dict[str, Any]:
    return gmail_message()

