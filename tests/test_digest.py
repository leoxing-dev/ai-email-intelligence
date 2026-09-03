from __future__ import annotations

from tests.conftest import gmail_message

from app.config import Settings
from app.services.digest_service import DigestService
from app.services.summarizer import LocalSummarizer


class StubGmailService:
    def __init__(self, messages):
        self.settings = Settings(max_messages=20)
        self._messages = messages

    def fetch_unread(self):
        return self._messages


def test_digest_groups_messages_and_computes_overlapping_counts():
    messages = [
        gmail_message(
            message_id="urgent-001",
            subject="Urgent synthetic assignment deadline",
            body="Action required: please submit the course assignment by 2026-09-02.",
        ),
        gmail_message(
            message_id="reply-001",
            subject="Synthetic meeting question",
            body="Could you reply with a preferred example time?",
        ),
        gmail_message(
            message_id="promo-001",
            sender="Offers <no-reply@example.test>",
            subject="Synthetic newsletter",
            body="A synthetic promotional update.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        ),
    ]
    service = DigestService(StubGmailService(messages), LocalSummarizer())

    digest = service.unread_digest()
    grouped_ids = {
        section.title: [message.message_id for message in section.messages]
        for section in digest.sections
    }

    assert grouped_ids["URGENT / TIME-SENSITIVE"] == ["urgent-001"]
    assert grouped_ids["NEEDS REPLY"] == ["reply-001"]
    assert grouped_ids["LOW PRIORITY / PROMOTIONAL"] == ["promo-001"]
    assert digest.counts.total_unread == 3
    assert digest.counts.urgent == 1
    assert digest.counts.action_required == 1
    assert digest.counts.possible_reply == 1
    assert digest.counts.low_priority == 1


def test_duplicate_surveys_are_grouped_without_losing_unread_count():
    messages = [
        gmail_message(
            message_id="survey-duplicate-001",
            subject="Synthetic satisfaction survey",
            body="Please take our optional satisfaction survey. Tell us what you think.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        ),
        gmail_message(
            message_id="survey-duplicate-002",
            subject="Synthetic satisfaction survey",
            body="Please take our optional satisfaction survey. Tell us what you think.",
            labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
        ),
    ]
    service = DigestService(StubGmailService(messages), LocalSummarizer())

    digest = service.unread_digest()
    promotional = next(
        section
        for section in digest.sections
        if section.title == "LOW PRIORITY / PROMOTIONAL"
    )

    assert len(promotional.messages) == 1
    assert promotional.messages[0].similar_count == 2
    assert "grouped 2 near-identical unread messages" in promotional.messages[0].reason
    assert digest.counts.total_unread == 2
    assert digest.counts.low_priority == 2


def test_legitimate_replies_in_same_thread_are_not_collapsed():
    messages = [
        gmail_message(
            message_id="reply-thread-001",
            subject="Synthetic discussion",
            body="Could you review the first synthetic proposal?",
        ),
        gmail_message(
            message_id="reply-thread-002",
            subject="Synthetic discussion",
            body="Could you review the revised synthetic proposal with new details?",
        ),
    ]
    service = DigestService(StubGmailService(messages), LocalSummarizer())

    digest = service.unread_digest()

    assert sum(len(section.messages) for section in digest.sections) == 2
    assert digest.counts.total_unread == 2


def test_only_derived_summaries_are_cached():
    service = DigestService(
        StubGmailService([gmail_message(body="Synthetic sensitive-like body text.")]),
        LocalSummarizer(),
    )

    service.sync()

    cached = service.unread_summaries(refresh=False)
    assert len(cached) == 1
    assert not hasattr(cached[0], "body_text")
    assert cached[0].message_id == "synthetic-message-001"


def test_sync_reports_parse_failures_without_exposing_payloads():
    service = DigestService(
        StubGmailService([gmail_message(), {"id": "broken-synthetic-message"}]),
        LocalSummarizer(),
    )

    result = service.sync()

    assert result.fetched == 2
    assert result.processed == 1
