"""Read-only Gmail OAuth and unread-message retrieval."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import Settings
from app.security.redaction import hash_identifier
from app.services.email_parser import sanitize_gmail_message_in_place


logger = logging.getLogger(__name__)


class GmailMessagesResource(Protocol):
    def list(self, **kwargs: Any) -> Any: ...

    def get(self, **kwargs: Any) -> Any: ...


class GmailUsersResource(Protocol):
    def messages(self) -> GmailMessagesResource: ...


class GmailApi(Protocol):
    def users(self) -> GmailUsersResource: ...


def _write_token_private(path: Path, token_json: str) -> None:
    """Atomically write an OAuth token with restrictive permissions where supported."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token_json)
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            logger.warning("could not tighten token file permissions")
    finally:
        if temporary.exists():
            temporary.unlink()


def authenticate_readonly(settings: Settings) -> Credentials:
    """Authenticate locally using only the immutable Gmail read-only scope."""

    credentials: Credentials | None = None
    if settings.token_path.exists():
        try:
            token_info = json.loads(settings.token_path.read_text(encoding="utf-8"))
            stored_scopes = set(token_info.get("scopes", ()))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise PermissionError("OAuth token file is invalid") from exc
        if stored_scopes != set(settings.gmail_scopes):
            raise PermissionError("OAuth token scopes are not exactly Gmail read-only")
        credentials = Credentials.from_authorized_user_file(
            str(settings.token_path), list(settings.gmail_scopes)
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    elif not credentials or not credentials.valid:
        if not settings.credentials_path.is_file():
            raise FileNotFoundError(
                f"OAuth client file not found at {settings.credentials_path}. "
                "See README.md; never commit this file."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(settings.credentials_path), list(settings.gmail_scopes)
        )
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            open_browser=True,
            authorization_prompt_message=None,
        )

    effective_scopes = set(credentials.granted_scopes or credentials.scopes or ())
    if effective_scopes != set(settings.gmail_scopes):
        raise PermissionError("OAuth token scopes are not exactly Gmail read-only")

    _write_token_private(settings.token_path, credentials.to_json())
    logger.info("Gmail authentication completed with read-only scope")
    return credentials


def build_gmail_api(settings: Settings) -> GmailApi:
    """Build the official Gmail API client without discovery caching."""

    return build(
        "gmail",
        "v1",
        credentials=authenticate_readonly(settings),
        cache_discovery=False,
    )


class GmailService:
    """Retrieve unread inbox messages without modifying mailbox state."""

    def __init__(
        self,
        settings: Settings,
        api_factory: Callable[[Settings], GmailApi] = build_gmail_api,
    ) -> None:
        self.settings = settings
        self._api_factory = api_factory

    def fetch_unread(self) -> list[dict[str, Any]]:
        """Fetch up to the configured cap, excluding attachment byte requests."""

        api = self._api_factory(self.settings)
        messages_resource = api.users().messages()
        message_refs: list[dict[str, str]] = []
        page_token: str | None = None

        while len(message_refs) < self.settings.max_messages:
            page_size = min(100, self.settings.max_messages - len(message_refs))
            response = messages_resource.list(
                userId="me",
                q=self.settings.query,
                maxResults=page_size,
                pageToken=page_token,
                includeSpamTrash=False,
            ).execute()
            message_refs.extend(response.get("messages", ()))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        payloads: list[dict[str, Any]] = []
        for ref in message_refs[: self.settings.max_messages]:
            message_id = ref["id"]
            payload = sanitize_gmail_message_in_place(
                messages_resource.get(
                    userId="me",
                    id=message_id,
                    format="full",
                ).execute()
            )
            payloads.append(payload)
            logger.info("fetched message_id hash=%s", hash_identifier(message_id))

        logger.info("fetched %d unread messages", len(payloads))
        return payloads
