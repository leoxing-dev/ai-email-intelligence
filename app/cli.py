"""Command-line interface for local unread summaries and digests."""

from __future__ import annotations

import argparse
import json
import sys

from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.security.logging import configure_logging
from app.services.digest_service import DigestService
from app.services.gmail_service import GmailService
from app.services.summarizer import LocalSummarizer


def _service() -> DigestService:
    settings = get_settings()
    configure_logging(settings.log_level)
    return DigestService(
        GmailService(settings), LocalSummarizer(settings.default_timezone)
    )


def _print_digest(service: DigestService, as_json: bool) -> None:
    digest = service.unread_digest(refresh=True)
    if as_json:
        print(digest.model_dump_json(indent=2))
        return

    for section in digest.sections:
        print(f"\n{section.title} ({len(section.messages)})")
        for item in section.messages:
            domain = f" [{item.sender_domain}]" if item.sender_domain else ""
            print(f"- {item.subject}")
            print(f"  From: {item.sender_display}{domain}")
            print(f"  Received: {item.received_at.isoformat()}")
            print(f"  Summary: {item.short_summary}")
            if item.similar_count > 1:
                print(f"  Similar unread messages: {item.similar_count}")
            print(
                f"  Priority: {item.priority.value}; action={item.action_kind.value}; "
                f"reply={item.needs_reply.value}; type={item.email_type.value}"
            )
            for detected in item.detected_dates:
                interpreted = (
                    detected.interpreted_at.isoformat()
                    if detected.interpreted_at
                    else detected.interpreted_date.isoformat()
                    if detected.interpreted_date
                    else "uncertain"
                )
                print(
                    f"  Date: {detected.text} ({interpreted}; "
                    f"type={detected.semantic_type.value}; "
                    f"confidence={detected.confidence.value})"
                )
            if item.contains_event:
                registration_deadline = (
                    item.registration_deadline.isoformat()
                    if item.registration_deadline
                    else "unknown"
                )
                print(
                    f"  Event: {item.event_status.value}; "
                    f"attendance={item.attendance_required.value}; "
                    f"registration_available={item.registration_available.value}; "
                    f"registration_required={item.registration_required.value}; "
                    f"registration_completed={item.registration_completed.value}; "
                    f"registration_deadline={registration_deadline}"
                )
            print(f"  Reason: {item.reason}")

    counts = digest.counts
    print("\nCOUNTS")
    print(
        f"total={counts.total_unread} urgent={counts.urgent} "
        f"action={counts.action_required} possible_reply={counts.possible_reply} "
        f"informational={counts.informational} low_priority={counts.low_priority} "
        f"uncertain={counts.uncertain}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Local, read-only Gmail unread digest. No external AI is used.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    digest = subparsers.add_parser("digest", help="Generate a fresh unread digest")
    digest.add_argument("--json", action="store_true", help="Emit structured JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "digest":
            _print_digest(_service(), args.json)
        return 0
    except FileNotFoundError:
        print("Gmail OAuth is not configured. See README.md.", file=sys.stderr)
        return 2
    except PermissionError:
        print("OAuth credentials violate the read-only scope policy.", file=sys.stderr)
        return 3
    except RefreshError:
        print("Gmail authorization expired or was revoked.", file=sys.stderr)
        return 4
    except (HttpError, TransportError):
        print("Gmail could not be reached or rejected the read-only request.", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
