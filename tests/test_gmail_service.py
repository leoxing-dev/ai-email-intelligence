from __future__ import annotations

import json

import pytest

from tests.conftest import encoded, gmail_message

from app.config import READONLY_GMAIL_SCOPE, Settings
from app.services.gmail_service import GmailService, authenticate_readonly


class Executable:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeMessagesResource:
    def __init__(self, message_payload=None):
        self.list_calls = []
        self.get_calls = []
        self.message_payload = message_payload

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return Executable({"messages": [{"id": "synthetic-id"}]})

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return Executable(
            self.message_payload or {"id": kwargs["id"], "payload": {}}
        )


class FakeApi:
    def __init__(self, messages):
        self._messages = messages

    def users(self):
        return self

    def messages(self):
        return self._messages


class OrderedMessagesResource(FakeMessagesResource):
    def __init__(self, count):
        super().__init__()
        self.message_refs = [
            {"id": f"synthetic-{index:03d}"} for index in range(count)
        ]

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return Executable({"messages": self.message_refs})


def test_only_read_operations_are_used_for_unread_retrieval():
    resource = FakeMessagesResource()
    settings = Settings(max_messages=10)
    service = GmailService(settings, api_factory=lambda _: FakeApi(resource))

    result = service.fetch_unread()

    assert result == [{"id": "synthetic-id", "payload": {}}]
    assert resource.list_calls[0]["q"] == "in:inbox is:unread"
    assert resource.list_calls[0]["includeSpamTrash"] is False
    assert resource.get_calls == [
        {"userId": "me", "id": "synthetic-id", "format": "full"}
    ]
    assert not hasattr(resource, "modify")
    assert settings.gmail_scopes == (READONLY_GMAIL_SCOPE,)


def test_default_query_remains_unread_inbox(monkeypatch):
    monkeypatch.delenv("GMAIL_ASSISTANT_QUERY", raising=False)
    monkeypatch.delenv("GMAIL_ASSISTANT_UNREAD_QUERY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.query == "in:inbox is:unread"


def test_inbox_query_and_limit_can_be_overridden_without_reordering(monkeypatch):
    monkeypatch.setenv("GMAIL_ASSISTANT_QUERY", "in:inbox")
    monkeypatch.setenv("GMAIL_ASSISTANT_MAX_MESSAGES", "100")
    resource = OrderedMessagesResource(count=120)
    settings = Settings(_env_file=None)
    service = GmailService(settings, api_factory=lambda _: FakeApi(resource))

    result = service.fetch_unread()

    assert settings.query == "in:inbox"
    assert settings.max_messages == 100
    assert resource.list_calls == [
        {
            "userId": "me",
            "q": "in:inbox",
            "maxResults": 100,
            "pageToken": None,
            "includeSpamTrash": False,
        }
    ]
    assert [message["id"] for message in result] == [
        f"synthetic-{index:03d}" for index in range(100)
    ]
    assert len(resource.get_calls) == 100
    assert all(call["format"] == "full" for call in resource.get_calls)
    assert not hasattr(resource, "modify")
    assert not hasattr(resource, "trash")
    assert not hasattr(resource, "delete")
    assert not hasattr(resource, "attachments")
    assert settings.gmail_scopes == (READONLY_GMAIL_SCOPE,)


def test_legacy_unread_query_environment_name_remains_supported(monkeypatch):
    monkeypatch.delenv("GMAIL_ASSISTANT_QUERY", raising=False)
    monkeypatch.setenv("GMAIL_ASSISTANT_UNREAD_QUERY", "in:inbox")

    settings = Settings(_env_file=None)

    assert settings.query == "in:inbox"
    assert settings.unread_query == settings.query


def test_token_with_any_broader_scope_is_rejected_before_use(tmp_path):
    token_path = tmp_path / "synthetic-token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "synthetic-access-token",
                "refresh_token": "synthetic-refresh-token",
                "token_uri": "https://oauth2.googleapis.test/token",
                "client_id": "synthetic-client-id",
                "client_secret": "synthetic-client-secret",
                "scopes": [
                    READONLY_GMAIL_SCOPE,
                    "https://mail.google.com/",
                ],
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        token_path=token_path,
        credentials_path=tmp_path / "unused-credentials.json",
    )

    with pytest.raises(PermissionError, match="exactly Gmail read-only"):
        authenticate_readonly(settings)


def test_attachment_data_is_stripped_at_gmail_service_boundary(caplog):
    marker = "SYNTHETIC_BOUNDARY_ATTACHMENT_BYTES"
    message = gmail_message(body="Synthetic visible message body.")
    message["payload"] = {
        "mimeType": "multipart/mixed",
        "headers": message["payload"]["headers"],
        "body": {},
        "parts": [
            {
                "mimeType": "text/plain",
                "filename": "",
                "headers": [],
                "body": {"data": encoded("Synthetic visible message body.")},
            },
            {
                "mimeType": "application/pdf",
                "filename": "synthetic.pdf",
                "headers": [],
                "body": {"data": encoded(marker), "size": len(marker)},
            },
        ],
    }
    resource = FakeMessagesResource(message_payload=message)
    service = GmailService(
        Settings(max_messages=1), api_factory=lambda _: FakeApi(resource)
    )

    result = service.fetch_unread()

    attachment = result[0]["payload"]["parts"][1]
    assert "data" not in attachment["body"]
    assert attachment["attachment_present"] is True
    assert marker not in str(result)
    assert marker not in caplog.text
    assert not hasattr(resource, "attachments")


def test_oauth_flow_does_not_print_authorization_url(monkeypatch, tmp_path):
    credentials_path = tmp_path / "synthetic-credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")
    token_path = tmp_path / "synthetic-token.json"

    class SyntheticCredentials:
        valid = True
        expired = False
        refresh_token = "synthetic-refresh"
        granted_scopes = [READONLY_GMAIL_SCOPE]
        scopes = [READONLY_GMAIL_SCOPE]

        def to_json(self):
            return json.dumps(
                {
                    "scopes": [READONLY_GMAIL_SCOPE],
                    "token": "synthetic-token",
                }
            )

    class SyntheticFlow:
        def __init__(self):
            self.run_kwargs = None

        def run_local_server(self, **kwargs):
            self.run_kwargs = kwargs
            return SyntheticCredentials()

    flow = SyntheticFlow()
    monkeypatch.setattr(
        "app.services.gmail_service.InstalledAppFlow.from_client_secrets_file",
        lambda *args, **kwargs: flow,
    )

    authenticate_readonly(
        Settings(credentials_path=credentials_path, token_path=token_path)
    )

    assert flow.run_kwargs["authorization_prompt_message"] is None
    assert flow.run_kwargs["open_browser"] is True
