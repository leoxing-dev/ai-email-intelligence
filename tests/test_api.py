from fastapi.testclient import TestClient

from app.main import app, get_digest_service
from app.services.digest_service import DigestService
from app.services.summarizer import LocalSummarizer
from tests.conftest import gmail_message
from tests.test_digest import StubGmailService


def test_health_discloses_local_only_security_posture():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["external_ai_enabled"] is False
    assert response.json()["gmail_scope"].endswith("/gmail.readonly")
    assert response.headers["cache-control"] == "no-store"


def test_digest_response_contains_no_raw_body_field():
    synthetic_body = "Synthetic raw body marker that must not be returned as a field."
    service = DigestService(
        StubGmailService([gmail_message(body=synthetic_body)]), LocalSummarizer()
    )
    app.dependency_overrides[get_digest_service] = lambda: service
    try:
        response = TestClient(app).get("/digest/unread")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert '"body_text"' not in response.text
    assert response.headers["cache-control"] == "no-store"

