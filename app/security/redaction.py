"""Helpers for privacy-safe identifiers and defensive log redaction."""

import hashlib
import re


_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)((?:access|refresh)[_-]?token\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(client[_-]?secret\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,;]+"),
    re.compile(
        r"(?i)([?&](?:code|state|access_token|refresh_token|client_secret)=)"
        r"[^&\s\"']+"
    ),
    re.compile(r"(?i)(\b(?:code|state)\s*[=:]\s*)[^\s,;&\"']+"),
)


def hash_identifier(value: str) -> str:
    """Return a short, one-way identifier suitable for operational logs."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def redact_sensitive_text(value: str) -> str:
    """Defensively redact common credential forms from a log string."""

    redacted = value
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted
