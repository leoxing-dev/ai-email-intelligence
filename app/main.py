"""Local-only FastAPI interface for the Phase 1 unread digest."""

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Response
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.errors import HttpError

from app.config import READONLY_GMAIL_SCOPE, Settings, get_settings
from app.schemas.summary import EmailSummary, HealthResponse, SyncResult, UnreadDigest
from app.security.logging import configure_logging
from app.services.digest_service import DigestService
from app.services.gmail_service import GmailService
from app.services.summarizer import LocalSummarizer


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Local Gmail Unread Digest",
    version="0.1.0",
    description="Read-only Gmail retrieval with deterministic local analysis; no external AI.",
)


@app.middleware("http")
async def prevent_sensitive_caching(request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@lru_cache
def get_digest_service() -> DigestService:
    current = get_settings()
    return DigestService(
        GmailService(current), LocalSummarizer(current.default_timezone)
    )


def _safe_operation(operation):  # type: ignore[no-untyped-def]
    try:
        return operation()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Local Gmail OAuth setup is incomplete; see README.md.",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="OAuth credentials do not satisfy the Phase 1 read-only policy.",
        ) from exc
    except RefreshError as exc:
        raise HTTPException(
            status_code=401,
            detail="Local Gmail authorization expired or was revoked; re-authenticate locally.",
        ) from exc
    except (HttpError, TransportError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Gmail could not be reached or rejected the read-only request.",
        ) from exc


@app.get("/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(gmail_scope=READONLY_GMAIL_SCOPE)


@app.get("/unread", response_model=list[EmailSummary])
def unread(
    digest_service: DigestService = Depends(get_digest_service),
) -> list[EmailSummary]:
    """Return derived summaries only; raw bodies are never in the response schema."""

    return _safe_operation(lambda: digest_service.unread_summaries(refresh=True))


@app.get("/digest/unread", response_model=UnreadDigest)
def unread_digest(
    digest_service: DigestService = Depends(get_digest_service),
) -> UnreadDigest:
    """Fetch unread inbox messages and return a locally generated digest."""

    return _safe_operation(lambda: digest_service.unread_digest(refresh=True))


@app.post("/sync", response_model=SyncResult)
def sync(
    digest_service: DigestService = Depends(get_digest_service),
) -> SyncResult:
    """Refresh the in-memory derived-summary cache without modifying Gmail."""

    return _safe_operation(digest_service.sync)
