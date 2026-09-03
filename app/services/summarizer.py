"""Deterministic, explainable, local-only email analysis."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, tzinfo

from dateutil import parser as date_parser
from dateutil.tz import gettz, tzoffset

from app.config import DEFAULT_TIMEZONE
from app.schemas.email import ParsedEmail
from app.schemas.summary import (
    ActionKind,
    Assessment,
    Category,
    Confidence,
    DateSemanticType,
    DetectedDate,
    EmailSummary,
    EmailType,
    EventStatus,
    Priority,
)


_PACIFIC_TZINFOS = {
    "PDT": tzoffset("PDT", -7 * 3600),
    "PST": tzoffset("PST", -8 * 3600),
    "pdt": tzoffset("PDT", -7 * 3600),
    "pst": tzoffset("PST", -8 * 3600),
}


_URGENT_STYLE = re.compile(
    r"\b(?:urgent|immediate(?:ly)?|time[- ]sensitive|final notice|act now|limited time)\b",
    re.IGNORECASE,
)
_REQUIRED = re.compile(
    r"\b(?:action required|must|mandatory|required to|requirements?|"
    r"required (?:form|documentation|documents?|information)|"
    r"need(?:s)? to (?:complete|submit|provide)|incomplete requirements?|"
    r"non[- ]compliance|registration hold|failure to(?: complete)?|"
    r"no later than|complete by|submit by|respond by|reply by|payment due|"
    r"account will|enrollment will|hold will be placed)\b",
    re.IGNORECASE,
)
_RECOMMENDED = re.compile(
    r"\bplease (?:review|consider|check|confirm|schedule)\b", re.IGNORECASE
)
_OPTIONAL = re.compile(
    r"\b(?:optional|if (?:you are|you're|interested)|if you (?:want|choose|wish)|"
    r"you can|feel free to|register now|join us|explore|unlock|claim|save|earn|"
    r"buy now|upgrade|shop|refer a friend|get rewards|take (?:our|the) survey|"
    r"tell us what you think|don't miss out)\b",
    re.IGNORECASE,
)
_REPLY = re.compile(
    r"\b(?:please (?:reply|respond)|respond by|reply by|let me know|can you|could you)\b",
    re.IGNORECASE,
)
_PROMOTIONAL = re.compile(
    r"\b(?:limited time|special offer|promotion|promo code|deal|save \d+%|"
    r"discount|unlock|buy now|upgrade|shop now|explore|rewards?|"
    r"earn (?:points|rewards)|claim (?:your|a)|survey|"
    r"tell us what you think|don't miss out|exclusive offer|refer a friend)\b",
    re.IGNORECASE,
)
_ACCOUNT_SECURITY = re.compile(
    r"\b(?:account security|security alert|unusual sign[- ]in|suspicious (?:login|activity)|"
    r"password reset|verify (?:your )?(?:account|identity)|account (?:locked|compromised))\b",
    re.IGNORECASE,
)
_SAFETY_ADVISORY = re.compile(
    r"\b(?:safety advisory|campus alert|emergency information|weather advisory|"
    r"public safety|service disruption)\b",
    re.IGNORECASE,
)
_SAFETY_RECOMMENDATION = re.compile(
    r"\b(?:wear (?:a )?helmet|lock (?:your|the)|stay alert|take precautions|"
    r"use caution|avoid the area|remain vigilant)\b",
    re.IGNORECASE,
)
_MANDATORY_SAFETY = re.compile(
    r"\b(?:mandatory evacuation|must evacuate|evacuate immediately|"
    r"emergency order|shelter in place|do not enter|mandatory lockdown)\b",
    re.IGNORECASE,
)
_ACADEMIC = re.compile(
    r"\b(?:assignment|homework|course|class|exam|quiz|syllabus|professor|instructor|faculty)\b",
    re.IGNORECASE,
)
_ADMINISTRATIVE = re.compile(
    r"\b(?:financial aid|tuition|registration hold|administrative|compliance|"
    r"non[- ]compliance|immunization|student account|payment|tax|"
    r"verification document|required documentation|enrollment(?: problem)?|"
    r"graduation application)\b",
    re.IGNORECASE,
)
_RECRUITING = re.compile(
    r"\b(?:career fair|recruiting|recruiter|job fair|interview|internship)\b",
    re.IGNORECASE,
)
_EVENT = re.compile(
    r"\b(?:event|career fair|job fair|meeting|appointment|interview|webinar|"
    r"interview session|information session|workshop|fair|session|seminar|panel|"
    r"open house|orientation|student welcome|welcome event|tech talk|expo|"
    r"reception|conference|meet\b.{0,30}\brecruiters?|takes place|scheduled for)\b",
    re.IGNORECASE,
)
_NEWSLETTER = re.compile(r"\b(?:newsletter|weekly digest|monthly update)\b", re.IGNORECASE)
_DIGEST_CONTAINER = re.compile(
    r"\b(?:(?:spam|daily|security|quarantine|newsletter|notification) digest|"
    r"security quarantine digest|quarantined message digest)\b",
    re.IGNORECASE,
)
_RECEIPT = re.compile(
    r"\b(?:receipt|order confirmation|payment received|transaction confirmation)\b",
    re.IGNORECASE,
)
_INFORMATIONAL = re.compile(
    r"\b(?:for your information|no action (?:is )?required|update|notice|announcement)\b",
    re.IGNORECASE,
)
_ATTENDANCE_REQUIRED = re.compile(
    r"\b(?:attendance (?:is )?required|must attend|mandatory attendance)\b",
    re.IGNORECASE,
)
_REGISTRATION_REQUIRED = re.compile(
    r"\b(?:registration (?:is )?required|must register|rsvp (?:is )?required)\b",
    re.IGNORECASE,
)
_NO_REGISTRATION = re.compile(r"\bno registration (?:is )?required\b", re.IGNORECASE)
_REGISTRATION_COMPLETE = re.compile(
    r"\b(?:(?:your )?registration (?:is |was )?(?:successful|confirmed|complete)|"
    r"you(?: are|'re) registered|rsvp (?:is )?confirmed)\b",
    re.IGNORECASE,
)
_REGISTRATION_OPTIONAL = re.compile(
    r"\b(?:registration (?:is )?optional|rsvp (?:is )?optional|"
    r"register here if you(?:'d| would) like to attend|"
    r"register (?:here )?if (?:you are|you're|interested)|"
    r"register (?:here )?if you (?:want|choose|wish))\b",
    re.IGNORECASE,
)
_REGISTRATION_AVAILABLE = re.compile(
    r"\b(?:registration (?:is )?(?:open|available)|register here|register online|"
    r"sign up|rsvp)\b",
    re.IGNORECASE,
)
_REGISTRATION_CONTEXT = re.compile(r"\b(?:registration|register|rsvp)\b", re.IGNORECASE)

_DEADLINE_CONTEXT = re.compile(
    r"\b(?:deadline|due(?: by)?|respond by|reply by|submit by|complete by|"
    r"required by|no later than|registration closes?)\b|"
    r"\b(?:submit|complete|respond|reply|finish|turn in|register|registration|rsvp)"
    r"\b.{0,60}\bby\b",
    re.IGNORECASE,
)
_PUBLICATION_CONTEXT = re.compile(
    r"\b(?:published|publication date|posted|issued|released)\b", re.IGNORECASE
)
_HISTORICAL_CONTEXT = re.compile(
    r"\b(?:was|occurred|previous|formerly|last attended|had been)\b", re.IGNORECASE
)

_ADMINISTRATIVE_CONSEQUENCE = re.compile(
    r"\b(?:registration hold|account (?:suspension|will be suspended)|"
    r"enrollment (?:problem|will be affected)|hold will be placed|"
    r"failure to complete|remain incomplete|missing required documentation)\b",
    re.IGNORECASE,
)
_ACTION_COMPLETE = re.compile(
    r"\b(?:no further action (?:is )?required|already completed|"
    r"requirements? (?:has|have) been (?:completed|satisfied)|"
    r"required documentation has been received|we (?:have )?received your documentation)\b",
    re.IGNORECASE,
)
_CONDITIONAL_ACTION = re.compile(
    r"\b(?:if you (?:want|choose|wish|plan)|if (?:you are|you're )?interested|"
    r"optional)\b.{0,100}\b(?:submit|register|complete|provide|apply)\b",
    re.IGNORECASE,
)
_DEADLINE_ACTION = re.compile(
    r"\b(?:submit|complete|respond|reply|finish|turn in|register|rsvp|"
    r"pay|provide|file)\b.{0,80}\b(?:by|deadline|due)\b|"
    r"\b(?:due|deadline)\b.{0,80}\b(?:submit|complete|respond|reply|pay|provide|file)\b",
    re.IGNORECASE,
)
_REGISTER_BY = re.compile(r"\b(?:register|rsvp)\b.{0,40}\bby\b", re.IGNORECASE)

_MONTH_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?"
    r"(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)"
    r"(?:\s+(?:PDT|PST))?)?\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?"
    r"(?:\s*(?:Z|[+-]\d{2}:?\d{2}))?)?\b",
    re.IGNORECASE,
)
_NUMERIC_DATE = re.compile(
    r"\b\d{1,2}/\d{1,2}(?:/(?:\d{2}|\d{4}))?(?:\s+(?:at\s+)?"
    r"\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)"
    r"(?:\s+(?:PDT|PST))?)?\b",
    re.IGNORECASE,
)
_RELATIVE_DATE = re.compile(
    r"\b(?:today|tomorrow|tonight|this (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)|"
    r"next (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))"
    r"(?:\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)"
    r"(?:\s+(?:PDT|PST))?)?\b",
    re.IGNORECASE,
)

_BOILERPLATE_LINES = (
    re.compile(r"^(?:view|read) (?:this )?email (?:in|as) (?:a )?(?:browser|web page)\.?$", re.I),
    re.compile(r"^view (?:in|online in) (?:your )?browser\.?$", re.I),
    re.compile(r"^to view this email as a web page(?:,?\s*click here)?\.?$", re.I),
    re.compile(r"^this email was sent on behalf of\b.*$", re.I),
    re.compile(r"^(?:caution:\s*)?external (?:email|sender).*$", re.I),
    re.compile(r"^(?:caution:\s*)?this email originated from outside\b.*$", re.I),
    re.compile(r"^this message originated (?:from )?outside\b.*$", re.I),
    re.compile(r"^\[?external\]?$", re.I),
    re.compile(r"^(?:unsubscribe|manage (?:email )?preferences)(?:\s*[|·-].*)?$", re.I),
    re.compile(r"^you are receiving this email because.*$", re.I),
    re.compile(r"^(?:privacy policy|update subscription preferences)\.?$", re.I),
)


class EmailSummarizer(ABC):
    """Interface for local or future institution-approved summarizers."""

    @abstractmethod
    def summarize(self, email: ParsedEmail) -> EmailSummary:
        """Produce derived fields without exposing the raw body."""


def preprocess_body(text: str) -> str:
    """Remove narrow, common boilerplate before deterministic extraction."""

    text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)
    retained: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if any(pattern.match(line) for pattern in _BOILERPLATE_LINES):
            continue
        retained.append(line)
    return "\n".join(retained)


def _sentences(text: str) -> list[str]:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed:
        return []
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", collapsed) if item.strip()]


def _short_summary(email: ParsedEmail, clean_body: str) -> str:
    candidates = _sentences(clean_body)
    if not candidates:
        return f"No usable message body was found; review the subject: {email.subject[:160]}"
    meaningful = next((item for item in candidates if len(item) >= 20), candidates[0])
    if len(meaningful) <= 240:
        return meaningful
    clipped = meaningful[:237].rsplit(" ", 1)[0]
    return f"{clipped}…"


def _parse_explicit_date(
    phrase: str, received_at: datetime, pattern_kind: str
) -> tuple[date | None, datetime | None, Confidence]:
    has_clock_time = bool(
        re.search(
            r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b",
            phrase,
            re.IGNORECASE,
        )
        or re.search(r"[T ]\d{1,2}:\d{2}", phrase)
    )
    if pattern_kind == "relative":
        lowered = phrase.lower()
        if lowered.startswith(("today", "tonight")):
            base = received_at
            relative_label = lowered.split(maxsplit=1)[0]
        elif lowered.startswith("tomorrow"):
            base = received_at + timedelta(days=1)
            relative_label = "tomorrow"
        elif match := re.match(
            r"(this|next) (monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            lowered,
        ):
            weekdays = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            target = weekdays[match.group(2)]
            days_ahead = (target - received_at.weekday()) % 7
            if match.group(1) == "next" and days_ahead == 0:
                days_ahead = 7
            base = received_at + timedelta(days=days_ahead)
            relative_label = match.group(0)
        else:
            return None, None, Confidence.LOW
        time_phrase = phrase[len(relative_label) :].strip()
        if not time_phrase:
            return base.date(), None, Confidence.MEDIUM
        try:
            parsed = date_parser.parse(
                time_phrase,
                default=base,
                fuzzy=True,
                tzinfos=_PACIFIC_TZINFOS,
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=received_at.tzinfo)
            return parsed.date(), parsed if has_clock_time else None, Confidence.MEDIUM
        except (ValueError, OverflowError):
            return None, None, Confidence.LOW

    if not re.search(r"\b\d{4}\b", phrase):
        return None, None, Confidence.MEDIUM
    try:
        parsed = date_parser.parse(
            phrase,
            default=received_at,
            fuzzy=False,
            tzinfos=_PACIFIC_TZINFOS,
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=received_at.tzinfo)
        confidence = Confidence.MEDIUM if pattern_kind == "numeric" else Confidence.HIGH
        return parsed.date(), parsed if has_clock_time else None, confidence
    except (ValueError, OverflowError):
        return None, None, Confidence.LOW


def _surrounding_sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind("?", 0, start))
    right_candidates = [position for delimiter in ".?\n" if (position := text.find(delimiter, end)) >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right + 1]


def _date_context(text: str, start: int, end: int, subject_end: int) -> str:
    """Return subject-wide or narrow nearby context for a detected date."""

    if start < subject_end:
        return text[:subject_end]
    sentence = _surrounding_sentence(text, start, end)
    if _EVENT.search(sentence) or _DEADLINE_CONTEXT.search(sentence):
        return sentence
    nearby = text[max(subject_end + 1, start - 100) : min(len(text), end + 100)]
    if _EVENT.search(nearby) or _REGISTRATION_CONTEXT.search(nearby):
        return nearby
    return sentence


def _date_semantic(
    context: str,
    interpreted_date: date | None,
    received_at: datetime,
    promotional: bool,
) -> DateSemanticType:
    if _DEADLINE_CONTEXT.search(context):
        if _REGISTRATION_CONTEXT.search(context):
            return DateSemanticType.REGISTRATION_DEADLINE
        return DateSemanticType.DEADLINE
    if _PUBLICATION_CONTEXT.search(context):
        return DateSemanticType.PUBLICATION_DATE
    if _HISTORICAL_CONTEXT.search(context) or (
        interpreted_date is not None and interpreted_date < received_at.date()
    ):
        return DateSemanticType.HISTORICAL_DATE
    if _EVENT.search(context):
        return DateSemanticType.EVENT_TIME
    if promotional:
        return DateSemanticType.PROMOTION_DATE
    return DateSemanticType.REFERENCED_DATE


def detect_dates(
    email: ParsedEmail,
    *,
    clean_body: str | None = None,
    promotional: bool = False,
    local_timezone: tzinfo | None = None,
) -> list[DetectedDate]:
    """Detect dates and label their semantics without turning all dates into deadlines."""

    body = clean_body if clean_body is not None else preprocess_body(email.body_text)
    text = f"{email.subject}\n{body}"
    zone = local_timezone or gettz(DEFAULT_TIMEZONE)
    if zone is None:  # Defensive only; the default is validated at startup.
        raise ValueError("configured timezone is unavailable")
    local_received_at = email.received_at.astimezone(zone)
    subject_end = len(email.subject)
    matches: list[tuple[int, int, str, str]] = []
    for kind, pattern in (
        ("iso", _ISO_DATE),
        ("month", _MONTH_DATE),
        ("numeric", _NUMERIC_DATE),
        ("relative", _RELATIVE_DATE),
    ):
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < existing[1] and end > existing[0] for existing in matches):
                continue
            matches.append((start, end, match.group(0), kind))

    results: list[DetectedDate] = []
    seen: set[str] = set()
    context_labels = {
        DateSemanticType.DEADLINE: "Deadline-related date",
        DateSemanticType.REGISTRATION_DEADLINE: "Registration deadline",
        DateSemanticType.EVENT_TIME: "Event date or time",
        DateSemanticType.HISTORICAL_DATE: "Historical date",
        DateSemanticType.PUBLICATION_DATE: "Publication date",
        DateSemanticType.PROMOTION_DATE: "Promotional date",
        DateSemanticType.REFERENCED_DATE: "Referenced date",
        DateSemanticType.UNKNOWN: "Date with uncertain purpose",
    }
    for start, end, phrase, kind in sorted(matches):
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        interpreted_date, interpreted_at, confidence = _parse_explicit_date(
            phrase, local_received_at, kind
        )
        semantic = _date_semantic(
            _date_context(text, start, end, subject_end),
            interpreted_date,
            local_received_at,
            promotional,
        )
        if (
            semantic is DateSemanticType.EVENT_TIME
            and interpreted_date is None
            and kind in {"month", "numeric"}
        ):
            try:
                inferred = date_parser.parse(
                    phrase,
                    default=local_received_at,
                    fuzzy=False,
                    tzinfos=_PACIFIC_TZINFOS,
                )
                interpreted_date = inferred.date()
                if re.search(
                    r"\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b",
                    phrase,
                    re.IGNORECASE,
                ):
                    interpreted_at = inferred
                confidence = Confidence.MEDIUM
            except (ValueError, OverflowError):
                pass
        results.append(
            DetectedDate(
                text=phrase,
                interpreted_date=interpreted_date,
                interpreted_at=interpreted_at,
                semantic_type=semantic,
                confidence=confidence,
                context=context_labels[semantic],
            )
        )
    return results[:10]


class LocalSummarizer(EmailSummarizer):
    """Conservative heuristic analyzer; all computation remains local."""

    def __init__(self, timezone_name: str = DEFAULT_TIMEZONE) -> None:
        local_timezone = gettz(timezone_name)
        if local_timezone is None:
            raise ValueError("configured timezone is unavailable")
        self._local_timezone = local_timezone

    def summarize(self, email: ParsedEmail) -> EmailSummary:
        clean_body = preprocess_body(email.body_text)
        text = f"{email.subject}\n{clean_body}"
        digest_container = bool(_DIGEST_CONTAINER.search(email.subject))
        analysis_text = email.subject if digest_container else text
        local_received_at = email.received_at.astimezone(self._local_timezone)

        promotional = email.is_promotional or bool(_PROMOTIONAL.search(analysis_text))
        security = bool(_ACCOUNT_SECURITY.search(analysis_text))
        safety_advisory = bool(_SAFETY_ADVISORY.search(analysis_text))
        safety_recommendation = safety_advisory and bool(
            _SAFETY_RECOMMENDATION.search(analysis_text)
        )
        mandatory_safety = bool(_MANDATORY_SAFETY.search(analysis_text))
        sender_role = bool(re.search(r"\b(?:professor|instructor)\b", email.sender_display, re.I))
        academic = bool(_ACADEMIC.search(analysis_text)) or (
            sender_role
            and bool(_REPLY.search(analysis_text) or _REQUIRED.search(analysis_text))
        )
        administrative = bool(_ADMINISTRATIVE.search(analysis_text))
        recruiting = bool(_RECRUITING.search(analysis_text))
        event_signal = not digest_container and bool(_EVENT.search(analysis_text))
        newsletter = bool(_NEWSLETTER.search(analysis_text))
        receipt = bool(_RECEIPT.search(analysis_text))
        explicit_reply = bool(_REPLY.search(analysis_text))
        optional_signal = bool(_OPTIONAL.search(analysis_text)) or promotional
        action_completed = bool(_ACTION_COMPLETE.search(analysis_text))
        conditional_action = bool(_CONDITIONAL_ACTION.search(analysis_text))
        explicit_required = bool(_REQUIRED.search(analysis_text)) and not action_completed

        dates = (
            []
            if digest_container
            else detect_dates(
                email,
                clean_body=clean_body,
                promotional=promotional,
                local_timezone=self._local_timezone,
            )
        )
        has_deadline = any(
            item.semantic_type
            in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE}
            for item in dates
        )
        future_deadline_dates = [
            item
            for item in dates
            if item.semantic_type
            in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE}
            and (
                item.interpreted_date
                or (item.interpreted_at.date() if item.interpreted_at else None)
            )
            and (
                item.interpreted_date
                or item.interpreted_at.date()  # type: ignore[union-attr]
            )
            >= local_received_at.date()
        ]
        has_future_deadline = bool(future_deadline_dates)
        conditional_deadline = has_future_deadline and conditional_action
        contains_event = event_signal or any(
            item.semantic_type is DateSemanticType.EVENT_TIME for item in dates
        )
        event_date = next(
            (
                item.interpreted_at or item.interpreted_date
                for item in dates
                if item.semantic_type is DateSemanticType.EVENT_TIME
            ),
            None,
        )

        event_dates = [
            item.interpreted_at or item.interpreted_date
            for item in dates
            if item.semantic_type is DateSemanticType.EVENT_TIME
            and (item.interpreted_at or item.interpreted_date) is not None
        ]
        normalized_event_dates = [
            value.date() if isinstance(value, datetime) else value for value in event_dates
        ]
        if any(value > local_received_at.date() for value in normalized_event_dates):
            event_status = EventStatus.UPCOMING
        elif any(value == local_received_at.date() for value in normalized_event_dates):
            event_status = EventStatus.ONGOING
        elif normalized_event_dates or (
            event_signal
            and any(
                item.semantic_type is DateSemanticType.HISTORICAL_DATE for item in dates
            )
        ):
            event_status = EventStatus.PAST
        else:
            event_status = EventStatus.UNCERTAIN

        no_registration = bool(_NO_REGISTRATION.search(analysis_text))
        registration_complete = bool(_REGISTRATION_COMPLETE.search(analysis_text))
        registration_optional = bool(_REGISTRATION_OPTIONAL.search(analysis_text)) or (
            conditional_action and bool(_REGISTRATION_CONTEXT.search(analysis_text))
        )
        registration_available_signal = bool(
            _REGISTRATION_AVAILABLE.search(analysis_text)
        )
        registration_deadline = next(
            (
                item.interpreted_at or item.interpreted_date
                for item in dates
                if item.semantic_type is DateSemanticType.REGISTRATION_DEADLINE
            ),
            None,
        )
        has_registration_deadline = any(
            item.semantic_type is DateSemanticType.REGISTRATION_DEADLINE
            for item in dates
        )
        registration_required_signal = (
            bool(_REGISTRATION_REQUIRED.search(analysis_text))
            or bool(has_registration_deadline and _REGISTER_BY.search(analysis_text))
        ) and not (
            no_registration
            or registration_complete
            or registration_optional
            or conditional_action
        )

        meaningful_context = security or academic or administrative
        active_event = event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}
        administrative_consequence = administrative and bool(
            _ADMINISTRATIVE_CONSEQUENCE.search(analysis_text)
        )
        deadline_action = bool(_DEADLINE_ACTION.search(analysis_text))
        applicable_deadline = (
            has_future_deadline and not conditional_deadline and not action_completed
        )
        independent_obligation = (
            mandatory_safety
            or administrative_consequence
            or registration_required_signal
            or (security and explicit_required)
            or (academic and (explicit_required or applicable_deadline))
            or (administrative and (explicit_required or applicable_deadline))
            or (applicable_deadline and deadline_action and meaningful_context)
        )
        marketing_without_obligation = promotional and not independent_obligation
        required = (
            (
                explicit_required
                and (meaningful_context or deadline_action or administrative_consequence)
                and not conditional_action
            )
            or administrative_consequence
            or (
                applicable_deadline
                and (meaningful_context or explicit_reply or deadline_action)
            )
            or (
                security
                and bool(
                    re.search(
                        r"\b(?:verify|reset|secure|change)\b", analysis_text, re.I
                    )
                )
            )
            or mandatory_safety
            or (active_event and bool(_ATTENDANCE_REQUIRED.search(analysis_text)))
            or (active_event and registration_required_signal)
        ) and not action_completed and not marketing_without_obligation

        if required:
            action_kind = ActionKind.REQUIRED
        elif digest_container:
            action_kind = ActionKind.NONE
        elif action_completed or registration_complete:
            action_kind = ActionKind.NONE
        elif conditional_deadline:
            action_kind = ActionKind.OPTIONAL
        elif applicable_deadline:
            action_kind = ActionKind.RECOMMENDED
        elif active_event and registration_available_signal and not no_registration:
            action_kind = ActionKind.OPTIONAL
        elif safety_recommendation:
            action_kind = ActionKind.RECOMMENDED
        elif _RECOMMENDED.search(analysis_text) and (
            meaningful_context or safety_advisory
        ):
            action_kind = ActionKind.RECOMMENDED
        elif optional_signal:
            action_kind = ActionKind.OPTIONAL
        elif (
            newsletter
            or receipt
            or contains_event
            or safety_advisory
            or _INFORMATIONAL.search(analysis_text)
        ):
            action_kind = ActionKind.NONE
        else:
            action_kind = ActionKind.UNCERTAIN

        needs_action = (
            Assessment.TRUE
            if action_kind in {ActionKind.REQUIRED, ActionKind.RECOMMENDED}
            else Assessment.FALSE
            if action_kind in {ActionKind.OPTIONAL, ActionKind.NONE}
            else Assessment.UNCERTAIN
        )

        if digest_container or email.is_automated or (promotional and not security):
            needs_reply = Assessment.FALSE
        elif explicit_reply:
            needs_reply = Assessment.TRUE
        elif "?" in clean_body:
            needs_reply = Assessment.UNCERTAIN
        elif newsletter or receipt or contains_event or safety_advisory:
            needs_reply = Assessment.FALSE
        else:
            needs_reply = Assessment.UNCERTAIN

        if digest_container:
            email_type = EmailType.DIGEST
        elif security or safety_advisory or mandatory_safety:
            email_type = EmailType.SECURITY
        elif administrative:
            email_type = EmailType.ADMINISTRATIVE
        elif academic:
            email_type = EmailType.ACADEMIC
        elif newsletter:
            email_type = EmailType.NEWSLETTER
        elif recruiting:
            email_type = EmailType.RECRUITING
        elif contains_event:
            email_type = EmailType.EVENT
        elif receipt:
            email_type = EmailType.RECEIPT
        elif promotional:
            email_type = EmailType.PROMOTIONAL
        elif explicit_reply and not email.is_automated:
            email_type = EmailType.PERSONAL
        elif email.is_automated:
            email_type = EmailType.AUTOMATED
        else:
            email_type = EmailType.UNKNOWN

        urgent = mandatory_safety or (
            bool(_URGENT_STYLE.search(analysis_text))
            and (
                (security and required)
                or (required and has_deadline and meaningful_context)
            )
        )
        if urgent:
            priority = Priority.URGENT
        elif required or needs_reply is Assessment.TRUE or safety_advisory:
            priority = Priority.HIGH
        elif event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}:
            priority = Priority.NORMAL
        elif has_future_deadline:
            priority = Priority.NORMAL
        elif digest_container:
            priority = Priority.NORMAL
        elif promotional or newsletter:
            priority = Priority.LOW
        elif not clean_body:
            priority = Priority.UNKNOWN
        else:
            priority = Priority.NORMAL

        if priority is Priority.URGENT:
            category = Category.URGENT
        elif action_kind is ActionKind.REQUIRED:
            category = Category.ACTION_REQUIRED
        elif needs_reply is Assessment.TRUE:
            category = Category.REPLY_POSSIBLE
        elif event_status in {EventStatus.UPCOMING, EventStatus.ONGOING}:
            category = Category.INFORMATIONAL
        elif digest_container or (safety_advisory and action_kind is not ActionKind.REQUIRED):
            category = Category.INFORMATIONAL
        elif needs_action is Assessment.TRUE:
            category = Category.ACTION_REQUIRED
        elif has_future_deadline:
            category = Category.INFORMATIONAL
        elif promotional or newsletter:
            category = Category.PROMOTIONAL
        elif email.is_automated and not (newsletter or safety_advisory):
            category = Category.AUTOMATED_NOTIFICATION
        elif (
            newsletter
            or receipt
            or contains_event
            or safety_advisory
            or _INFORMATIONAL.search(analysis_text)
        ):
            category = Category.INFORMATIONAL
        else:
            category = Category.UNKNOWN

        if not contains_event:
            attendance_required = Assessment.FALSE
            registration_available = Assessment.FALSE
            registration_required = Assessment.FALSE
            registration_completed = (
                Assessment.TRUE if registration_complete else Assessment.UNCERTAIN
            )
        else:
            attendance_required = (
                Assessment.TRUE
                if _ATTENDANCE_REQUIRED.search(analysis_text)
                else Assessment.FALSE
                if re.search(
                    r"\battendance (?:is )?optional\b", analysis_text, re.I
                )
                else Assessment.UNCERTAIN
            )
            registration_required = (
                Assessment.TRUE
                if registration_required_signal
                else Assessment.FALSE
                if no_registration or registration_complete or registration_optional
                else Assessment.UNCERTAIN
            )
            registration_available = (
                Assessment.TRUE
                if registration_available_signal
                or registration_required_signal
                or registration_optional
                or registration_complete
                or has_registration_deadline
                else Assessment.FALSE
                if no_registration
                else Assessment.UNCERTAIN
            )
            registration_completed = (
                Assessment.TRUE if registration_complete else Assessment.FALSE
            )

        reasons: list[str] = []
        if urgent:
            reasons.append("urgent wording plus meaningful consequence")
        if action_kind is ActionKind.REQUIRED:
            reasons.append("required action semantics detected")
        elif action_kind is ActionKind.RECOMMENDED:
            reasons.append("important recommended action detected")
        elif action_kind is ActionKind.OPTIONAL:
            reasons.append("optional or promotional call-to-action")
        if has_deadline:
            reasons.append("deadline semantics detected")
        if conditional_deadline:
            reasons.append("conditional deadline applies only if the user chooses to participate")
        if action_completed:
            reasons.append("message says the administrative action is already complete")
        if contains_event:
            reasons.append("event semantics detected")
        if event_status is EventStatus.UPCOMING:
            reasons.append("upcoming event retained regardless of message format")
        if promotional and priority is Priority.LOW:
            reasons.append("promotional content without overriding user value")
        if safety_advisory and not required:
            reasons.append("high-value safety information without required action")
        if digest_container:
            reasons.append("digest/container entries were not treated as direct events or actions")
        if not reasons:
            reasons.append("no strong deterministic signal; manual review recommended")

        return EmailSummary(
            message_id=email.message_id,
            sender_display=email.sender_display,
            sender_domain=email.sender_domain,
            subject=email.subject,
            received_at=email.received_at,
            short_summary=(
                "Digest/container message; embedded entries require local review."
                if digest_container
                else _short_summary(email, clean_body)
            ),
            priority=priority,
            action_kind=action_kind,
            needs_action=needs_action,
            needs_reply=needs_reply,
            email_type=email_type,
            detected_dates=dates,
            contains_event=contains_event,
            event_time=event_date,
            event_status=event_status,
            attendance_required=attendance_required,
            registration_available=registration_available,
            registration_required=registration_required,
            registration_completed=registration_completed,
            registration_deadline=registration_deadline,
            category=category,
            reason="; ".join(reasons),
        )
