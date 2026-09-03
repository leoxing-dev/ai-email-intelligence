"""Safe Gmail MIME sanitization and parsing without attachment processing."""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

from app.schemas.email import ParsedEmail


MAX_BODY_CHARACTERS = 12_000
_THREAD_BOUNDARIES = (
    re.compile(r"^\s*On .+ wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}\s*$", re.IGNORECASE),
    re.compile(r"^\s*From:\s+.+$", re.IGNORECASE),
    re.compile(r"^\s*_{5,}\s*$"),
)
_SIGNATURE_BOUNDARY = re.compile(r"^\s*--\s*$")
_CSS_BLOCK = re.compile(
    r"(?ims)^[ \t]*(?:[.#][\w-]+|(?:body|table|tr|td|a|div|span|p)"
    r"[\w\s.#>:+~,\[\]=\"'-]{0,160})\s*\{[^{}]{0,4000}\}[ \t]*(?:\n|$)"
)


class EmailParseError(ValueError):
    """Raised when a Gmail message cannot be safely parsed."""


def _decode_base64url_bytes(data: str) -> bytes:
    """Decode Gmail base64url data without interpreting its MIME charset."""

    if not data:
        return b""
    padded = data + "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise EmailParseError("Message contained invalid base64url text") from exc


def decode_base64url(data: str) -> str:
    """Decode Gmail base64url text defensively as UTF-8."""

    return _decode_base64url_bytes(data).decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    """Convert HTML to readable text while discarding active and tracking content."""

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "canvas", "img"]):
        element.decompose()
    for element in list(soup.find_all(True)):
        # Decomposing a hidden parent also invalidates descendant Tag objects
        # already returned by find_all(). Skip those detached descendants.
        if element.attrs is None:
            continue
        inline_style = str(element.get("style", "")).replace(" ", "").lower()
        classes = {str(value).lower() for value in element.get("class", ())}
        if (
            element.has_attr("hidden")
            or str(element.get("aria-hidden", "")).lower() == "true"
            or classes.intersection({"preheader", "preview-text", "hidden"})
            or any(
                marker in inline_style
                for marker in (
                    "display:none",
                    "visibility:hidden",
                    "max-height:0",
                    "font-size:0",
                    "opacity:0",
                )
            )
        ):
            element.decompose()
    text = soup.get_text(separator="\n")
    return normalize_text(unescape(text))


def normalize_text(text: str) -> str:
    """Normalize whitespace and remove quoted history and likely signatures."""

    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)
    text = _CSS_BLOCK.sub("", text)
    retained: list[str] = []
    blank_pending = False

    for line in text.splitlines():
        clean_line = re.sub(r"[ \t]+", " ", line).strip()
        if any(pattern.match(clean_line) for pattern in _THREAD_BOUNDARIES):
            break
        if _SIGNATURE_BOUNDARY.match(clean_line) and retained:
            break
        if clean_line.startswith(">"):
            continue
        if not clean_line:
            blank_pending = bool(retained)
            continue
        if blank_pending:
            retained.append("")
            blank_pending = False
        retained.append(clean_line)

    return "\n".join(retained).strip()[:MAX_BODY_CHARACTERS]


def _decoded_header(value: str | None, default: str) -> str:
    if not value:
        return default
    try:
        return str(make_header(decode_header(value))).strip() or default
    except (LookupError, UnicodeDecodeError):
        return value.strip() or default


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header in payload.get("headers", ()):
        name = str(header.get("name", "")).lower()
        if name and name not in result:
            result[name] = str(header.get("value", ""))
    return result


def _header_value(part: dict[str, Any], name: str) -> str:
    for header in part.get("headers", ()):
        if str(header.get("name", "")).lower() == name.lower():
            return str(header.get("value", ""))
    return ""


def _is_attachment(part: dict[str, Any]) -> bool:
    if part.get("attachment_present"):
        return True
    if part.get("filename"):
        return True
    body = part.get("body", {})
    if isinstance(body, dict) and body.get("attachmentId"):
        return True

    mime_type = str(part.get("mimeType", "")).lower()
    disposition = _header_value(part, "content-disposition").strip().lower()
    content_type = _header_value(part, "content-type").lower()
    if disposition.startswith("attachment"):
        return True
    if disposition.startswith("inline") and (
        re.search(r"\bfilename\*?\s*=", disposition)
        or re.search(r"\bname\*?\s*=", content_type)
        or mime_type not in {"text/plain", "text/html"}
    ):
        return True
    if re.search(r"\bname\*?\s*=", content_type):
        return True
    return bool(
        mime_type
        and not mime_type.startswith("multipart/")
        and mime_type not in {"text/plain", "text/html"}
    )


def _sanitize_part_in_place(
    part: dict[str, Any], *, inside_attachment: bool = False
) -> None:
    """Discard encoded attachment content without decoding or copying it."""

    attachment = inside_attachment or _is_attachment(part)
    body = part.get("body")
    if attachment:
        part["attachment_present"] = True
        if isinstance(body, dict):
            body.pop("data", None)
            body.pop("attachmentId", None)

    for child in part.get("parts") or ():
        if isinstance(child, dict):
            _sanitize_part_in_place(child, inside_attachment=attachment)


def sanitize_gmail_message_in_place(message: dict[str, Any]) -> dict[str, Any]:
    """Strip attachment-part bytes immediately from a Gmail API response.

    The input object is mutated and returned so callers do not retain parallel raw
    and sanitized copies. Normal plain-text and HTML body parts are preserved.
    """

    payload = message.get("payload")
    if isinstance(payload, dict):
        _sanitize_part_in_place(payload)
    return message


def _part_charset(part: dict[str, Any]) -> str:
    for header in part.get("headers", ()):
        if str(header.get("name", "")).lower() != "content-type":
            continue
        match = re.search(
            r"charset\s*=\s*[\"']?([^;\s\"']+)",
            str(header.get("value", "")),
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    return "utf-8"


def _decode_part_text(part: dict[str, Any], data: str) -> str:
    raw = _decode_base64url_bytes(data)
    charset = _part_charset(part)
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _walk_text_parts(part: dict[str, Any]) -> Iterable[tuple[str, str]]:
    """Yield inline text MIME parts recursively; never request attachment IDs."""

    if _is_attachment(part):
        return

    mime_type = str(part.get("mimeType", "")).lower()
    body = part.get("body", {})
    data = body.get("data")
    if data and mime_type in {"text/plain", "text/html"}:
        yield mime_type, _decode_part_text(part, str(data))

    for child in part.get("parts", ()):
        yield from _walk_text_parts(child)


def _select_body(payload: dict[str, Any]) -> str:
    parts = list(_walk_text_parts(payload))
    plain_parts = [normalize_text(value) for mime, value in parts if mime == "text/plain"]
    usable_plain = [value for value in plain_parts if value]
    if usable_plain:
        return normalize_text("\n\n".join(usable_plain))

    html_parts = [html_to_text(value) for mime, value in parts if mime == "text/html"]
    usable_html = [value for value in html_parts if value]
    return normalize_text("\n\n".join(usable_html))


def _received_at(headers: dict[str, str], message: dict[str, Any]) -> datetime:
    raw_date = headers.get("date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (TypeError, ValueError, OverflowError):
            pass

    internal_date = message.get("internalDate")
    if internal_date is not None:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
        except (TypeError, ValueError, OverflowError):
            pass
    raise EmailParseError("Message has no valid received timestamp")


def parse_gmail_message(message: dict[str, Any]) -> ParsedEmail:
    """Parse one Gmail API message into an in-memory local model."""

    message_id = str(message.get("id", "")).strip()
    payload = message.get("payload")
    if not message_id or not isinstance(payload, dict):
        raise EmailParseError("Message is missing an ID or MIME payload")

    headers = _headers(payload)
    sender_header = _decoded_header(headers.get("from"), "Unknown sender")
    sender_name, sender_address = parseaddr(sender_header)
    sender_display = sender_name.strip() or sender_address.strip() or "Unknown sender"
    normalized_address = sender_address.lower().strip() or None
    sender_domain = None
    if normalized_address and "@" in normalized_address:
        sender_domain = normalized_address.rsplit("@", 1)[1]

    auto_submitted = headers.get("auto-submitted", "").lower()
    precedence = headers.get("precedence", "").lower()
    is_automated = bool(
        (auto_submitted and auto_submitted != "no")
        or precedence in {"bulk", "list", "junk"}
        or (normalized_address and re.search(r"(?:no-?reply|do-?not-?reply)", normalized_address))
    )
    labels = tuple(str(label) for label in message.get("labelIds", ()))
    is_promotional = "CATEGORY_PROMOTIONS" in labels or "list-unsubscribe" in headers

    return ParsedEmail(
        message_id=message_id,
        thread_id=str(message["threadId"]) if message.get("threadId") else None,
        sender_display=sender_display,
        sender_address=normalized_address,
        sender_domain=sender_domain,
        subject=_decoded_header(headers.get("subject"), "(No subject)"),
        received_at=_received_at(headers, message),
        body_text=_select_body(payload),
        label_ids=labels,
        is_automated=is_automated,
        is_promotional=is_promotional,
    )
