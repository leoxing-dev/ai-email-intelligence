"""Central privacy-preserving logging configuration."""

import logging

from app.security.redaction import redact_sensitive_text


class SensitiveDataFilter(logging.Filter):
    """Redact accidental credential-like strings before log emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        record.msg = redact_sensitive_text(rendered)
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure concise local logs with a defensive redaction filter."""

    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # google-auth-oauthlib logs the complete localhost callback request at INFO,
    # including short-lived authorization code and state query parameters.
    for logger_name in (
        "google_auth_oauthlib.flow",
        "oauthlib",
        "requests_oauthlib",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
