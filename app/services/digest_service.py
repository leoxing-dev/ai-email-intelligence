"""In-memory orchestration and digest grouping."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.summary import (
    ActionKind,
    Assessment,
    Category,
    DigestCounts,
    DigestSection,
    EmailSummary,
    EmailType,
    EventStatus,
    Priority,
    SyncResult,
    UnreadDigest,
)
from app.security.redaction import hash_identifier
from app.services.email_parser import EmailParseError, parse_gmail_message
from app.services.gmail_service import GmailService
from app.services.summarizer import EmailSummarizer


logger = logging.getLogger(__name__)

SECTION_TITLES = (
    "URGENT / TIME-SENSITIVE",
    "NEEDS ACTION",
    "NEEDS REPLY",
    "UPCOMING EVENTS",
    "IMPORTANT INFORMATIONAL",
    "OTHER INFORMATIONAL / NEWSLETTERS",
    "LOW PRIORITY / PROMOTIONAL",
    "REVIEW MANUALLY",
)


@dataclass(frozen=True)
class _AnalyzedMessage:
    summary: EmailSummary
    thread_id: str | None
    sender_key: str
    subject_key: str
    body_prefix: str


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _is_duplicate(candidate: _AnalyzedMessage, representative: _AnalyzedMessage) -> bool:
    if candidate.sender_key != representative.sender_key:
        return False
    if candidate.subject_key != representative.subject_key:
        return False
    if abs((candidate.summary.received_at - representative.summary.received_at).total_seconds()) > 600:
        return False
    same_thread = bool(
        candidate.thread_id
        and representative.thread_id
        and candidate.thread_id == representative.thread_id
    )
    same_body = bool(
        len(candidate.body_prefix) >= 20
        and candidate.body_prefix == representative.body_prefix
    )
    return same_body or (
        same_thread
        and candidate.summary.short_summary == representative.summary.short_summary
    )


def _group_duplicates(messages: list[_AnalyzedMessage]) -> list[EmailSummary]:
    groups: list[list[_AnalyzedMessage]] = []
    for message in messages:
        group = next(
            (items for items in groups if _is_duplicate(message, items[0])),
            None,
        )
        if group is None:
            groups.append([message])
        else:
            group.append(message)

    summaries: list[EmailSummary] = []
    for group in groups:
        representative = max(group, key=lambda item: item.summary.received_at).summary
        if len(group) > 1:
            representative = representative.model_copy(
                update={
                    "similar_count": len(group),
                    "reason": (
                        f"{representative.reason}; grouped {len(group)} "
                        "near-identical unread messages"
                    ),
                }
            )
        summaries.append(representative)
    return summaries


def section_title_for_summary(summary: EmailSummary) -> str:
    """Return the production digest section for one derived summary."""

    if summary.priority is Priority.URGENT or summary.category is Category.URGENT:
        return SECTION_TITLES[0]
    if (
        summary.action_kind is ActionKind.REQUIRED
        or (
            summary.event_status is EventStatus.UPCOMING
            and summary.registration_required is Assessment.TRUE
            and summary.registration_completed is not Assessment.TRUE
        )
        or (
            summary.needs_action is Assessment.TRUE
            and summary.category is Category.ACTION_REQUIRED
            and summary.event_status
            not in {EventStatus.UPCOMING, EventStatus.ONGOING}
        )
    ):
        return SECTION_TITLES[1]
    if summary.needs_reply is Assessment.TRUE:
        return SECTION_TITLES[2]
    if summary.event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}:
        return SECTION_TITLES[3]
    if (
        summary.category in {Category.INFORMATIONAL, Category.AUTOMATED_NOTIFICATION}
        and summary.priority is Priority.HIGH
    ):
        return SECTION_TITLES[4]
    if summary.category in {
        Category.INFORMATIONAL,
        Category.AUTOMATED_NOTIFICATION,
    } or (
        summary.email_type is EmailType.NEWSLETTER
        and summary.priority is not Priority.LOW
    ):
        return SECTION_TITLES[5]
    if summary.priority is Priority.LOW or summary.category is Category.PROMOTIONAL:
        return SECTION_TITLES[6]
    return SECTION_TITLES[7]


class DigestService:
    """Process Gmail payloads in memory and retain derived summaries only."""

    def __init__(self, gmail: GmailService, summarizer: EmailSummarizer) -> None:
        self._gmail = gmail
        self._summarizer = summarizer
        self._last_summaries: tuple[EmailSummary, ...] = ()
        self._last_sync_at: datetime | None = None
        self._last_fetch_count = 0
        self._last_processed_count = 0

    def analyze_unread(self) -> list[EmailSummary]:
        payloads = self._gmail.fetch_unread()
        self._last_fetch_count = len(payloads)
        analyzed: list[_AnalyzedMessage] = []
        for payload in payloads:
            message_id = str(payload.get("id", "missing"))
            try:
                parsed = parse_gmail_message(payload)
                summary = self._summarizer.summarize(parsed)
                analyzed.append(
                    _AnalyzedMessage(
                        summary=summary,
                        thread_id=parsed.thread_id,
                        sender_key=parsed.sender_address
                        or _normalized(parsed.sender_display),
                        subject_key=_normalized(parsed.subject),
                        body_prefix=_normalized(parsed.body_text)[:240],
                    )
                )
            except (EmailParseError, ValueError, TypeError):
                logger.warning(
                    "skipped unparseable message_id hash=%s",
                    hash_identifier(message_id),
                )
        self._last_processed_count = len(analyzed)
        summaries = _group_duplicates(analyzed)
        logger.info("processed %d message summaries", self._last_processed_count)
        if len(summaries) < self._last_processed_count:
            logger.info(
                "grouped %d near-duplicate messages",
                self._last_processed_count - len(summaries),
            )
        return summaries

    def sync(self) -> SyncResult:
        summaries = self.analyze_unread()
        now = datetime.now(UTC)
        self._last_summaries = tuple(summaries)
        self._last_sync_at = now
        return SyncResult(
            fetched=self._last_fetch_count,
            processed=self._last_processed_count,
            generated_at=now,
        )

    def unread_summaries(self, *, refresh: bool = True) -> list[EmailSummary]:
        if refresh or self._last_sync_at is None:
            self.sync()
        return list(self._last_summaries)

    def unread_digest(self, *, refresh: bool = True) -> UnreadDigest:
        summaries = self.unread_summaries(refresh=refresh)
        buckets: dict[str, list[EmailSummary]] = {title: [] for title in SECTION_TITLES}

        for summary in summaries:
            title = section_title_for_summary(summary)
            buckets[title].append(summary)

        for messages in buckets.values():
            messages.sort(key=lambda item: item.received_at, reverse=True)

        counts = DigestCounts(
            total_unread=sum(item.similar_count for item in summaries),
            urgent=sum(
                item.similar_count for item in summaries if item.priority is Priority.URGENT
            ),
            action_required=sum(
                item.similar_count
                for item in summaries
                if item.action_kind is ActionKind.REQUIRED
            ),
            possible_reply=sum(
                item.similar_count
                for item in summaries
                if item.needs_reply is Assessment.TRUE
            ),
            informational=sum(
                item.similar_count
                for item in summaries
                if item.category
                in {Category.INFORMATIONAL, Category.AUTOMATED_NOTIFICATION}
            ),
            low_priority=sum(
                item.similar_count
                for item in summaries
                if item.priority is Priority.LOW
                or item.category is Category.PROMOTIONAL
            ),
            uncertain=sum(
                item.similar_count
                for item in summaries
                if item.priority is Priority.UNKNOWN
                or item.needs_action is Assessment.UNCERTAIN
                or item.needs_reply is Assessment.UNCERTAIN
                or item.category is Category.UNKNOWN
            ),
        )
        return UnreadDigest(
            generated_at=self._last_sync_at or datetime.now(UTC),
            query=self._gmail.settings.query,
            sections=[
                DigestSection(title=title, messages=buckets[title])
                for title in SECTION_TITLES
            ],
            counts=counts,
        )
