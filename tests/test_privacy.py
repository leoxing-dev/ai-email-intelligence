from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from app.security.logging import SensitiveDataFilter, configure_logging
from app.security.redaction import hash_identifier, redact_sensitive_text


def test_identifier_hash_is_stable_and_does_not_reveal_input():
    synthetic_id = "synthetic-private-id"
    hashed = hash_identifier(synthetic_id)

    assert hashed == hash_identifier(synthetic_id)
    assert synthetic_id not in hashed
    assert len(hashed) == 12


def test_common_credentials_are_redacted():
    text = (
        "Authorization: Bearer synthetic-token "
        "refresh_token=synthetic-refresh client_secret=synthetic-secret"
    )
    redacted = redact_sensitive_text(text)

    assert "synthetic-token" not in redacted
    assert "synthetic-refresh" not in redacted
    assert "synthetic-secret" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_logging_filter_redacts_before_formatting():
    record = logging.LogRecord(
        "synthetic",
        logging.INFO,
        __file__,
        1,
        "access_token=%s",
        ("synthetic-secret-token",),
        None,
    )

    assert SensitiveDataFilter().filter(record) is True
    assert "synthetic-secret-token" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()


def test_oauth_callback_code_and_state_are_redacted():
    callback = (
        'GET /?state=synthetic-state-secret&code=synthetic-code-secret&scope=mail '
        'HTTP/1.1'
    )

    redacted = redact_sensitive_text(callback)

    assert "synthetic-state-secret" not in redacted
    assert "synthetic-code-secret" not in redacted
    assert "state=[REDACTED]" in redacted
    assert "code=[REDACTED]" in redacted


def test_oauth_library_info_logging_is_suppressed():
    configure_logging("INFO")

    assert logging.getLogger("google_auth_oauthlib.flow").isEnabledFor(logging.INFO) is False
    assert logging.getLogger("oauthlib").isEnabledFor(logging.INFO) is False
    assert logging.getLogger("app.services.gmail_service").isEnabledFor(logging.INFO) is True


def test_secret_and_email_export_files_are_git_ignored():
    root = Path(__file__).resolve().parents[1]
    candidates = [
        ".env",
        ".env.local",
        "credentials.json",
        "token.json",
        "synthetic.pem",
        "synthetic.key",
        "secrets/example.txt",
        "email-exports/example.eml",
        "mailbox.db",
        ".coverage",
        "local-run.log",
    ]
    for candidate in candidates:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", candidate],
            cwd=root,
            check=False,
        )
        assert result.returncode == 0, f"expected Git to ignore {candidate}"

    env_example = subprocess.run(
        ["git", "check-ignore", "--quiet", ".env.example"],
        cwd=root,
        check=False,
    )
    assert env_example.returncode == 1
