"""OpenAI Responses API adapter restricted to synthetic benchmark records."""

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

import httpx
from pydantic import ValidationError

from app.ai.base import ModelConfigurationError, ModelExtractor
from app.ai.config import ModelSettings
from app.ai.prompts.model_only_v1 import INSTRUCTIONS, PROMPT_VERSION
from app.ai.schemas import (
    ModelStructuredPrediction,
    ProviderMetadata,
    ProviderOutcome,
    ProviderResult,
    SyntheticEmailRecord,
    TokenUsage,
    ValidationIssue,
    ValidationStage,
    coarse_status_for_outcome,
    validate_prediction_domain,
    validation_issues_from_error,
)


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
INPUT_USD_PER_MILLION = 2.00
CACHED_INPUT_USD_PER_MILLION = 0.20
OUTPUT_USD_PER_MILLION = 12.00
_EMAIL_ADDRESS = re.compile(r"[A-Z0-9._%+-]+@([A-Z0-9.-]+)", re.IGNORECASE)


def _assert_synthetic(record: SyntheticEmailRecord) -> None:
    if record.source != "synthetic-email-benchmark-v2":
        raise ModelConfigurationError("OpenAI provider accepts synthetic benchmark v2 only")
    text = f"{record.sender}\n{record.subject}\n{record.body}"
    domains = [match.group(1).casefold() for match in _EMAIL_ADDRESS.finditer(text)]
    if any(not domain.endswith(".example") for domain in domains):
        raise ModelConfigurationError("synthetic record contains a non-example email domain")


def _safe_error_code(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"http_{response.status_code}"
    error = payload.get("error") if isinstance(payload, dict) else None
    code = error.get("code") or error.get("type") if isinstance(error, dict) else None
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(code))[:80] if code else "unknown"
    return f"http_{response.status_code}:{safe}"


def _output_text(payload: dict[str, Any]) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    return text
    return None


class OpenAIModelExtractor(ModelExtractor):
    """Synchronous adapter; callers may safely parallelize independent cases."""

    def __init__(self, settings: ModelSettings, *, client: httpx.Client | None = None):
        if settings.provider != "openai":
            raise ModelConfigurationError("OpenAI provider is not enabled")
        if settings.model != "gpt-5.6-terra":
            raise ModelConfigurationError("configured model must be gpt-5.6-terra")
        if settings.api_key is None:
            raise ModelConfigurationError("OPENAI_API_KEY is not set")
        self._settings = settings
        self._api_key = settings.api_key.get_secret_value()
        self._client = client

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider="openai",
            model=self._settings.model,
            model_version=self._settings.model,
            reasoning_effort=self._settings.reasoning_effort,
            service_tier=self._settings.service_tier,
            prompt_version=PROMPT_VERSION,
        )

    def extract(self, record: SyntheticEmailRecord) -> ProviderResult:
        _assert_synthetic(record)
        request_payload = {
            "model": self._settings.model,
            "reasoning": {"effort": self._settings.reasoning_effort},
            "service_tier": self._settings.service_tier,
            "store": False,
            "max_output_tokens": 5000,
            "instructions": INSTRUCTIONS,
            "input": json.dumps(record.model_dump(mode="json"), separators=(",", ":")),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "synthetic_email_prediction",
                    "strict": True,
                    "schema": ModelStructuredPrediction.model_json_schema(),
                }
            },
        }
        started = perf_counter()
        try:
            if self._client is None:
                with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
                    response = client.post(
                        OPENAI_RESPONSES_URL,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=request_payload,
                    )
            else:
                response = self._client.post(
                    OPENAI_RESPONSES_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=request_payload,
                )
        except httpx.TimeoutException:
            return self._failure(
                started, ProviderOutcome.PROVIDER_FAILURE, "timeout"
            )
        except httpx.HTTPError:
            return self._failure(
                started, ProviderOutcome.PROVIDER_FAILURE, "network_error"
            )
        if not response.is_success:
            return self._failure(
                started,
                ProviderOutcome.PROVIDER_FAILURE,
                _safe_error_code(response),
            )
        try:
            payload = response.json()
        except ValueError:
            return self._failure(
                started,
                ProviderOutcome.PROVIDER_FAILURE,
                "invalid_response_json",
            )
        if not isinstance(payload, dict):
            return self._failure(
                started,
                ProviderOutcome.PROVIDER_FAILURE,
                "invalid_response_shape",
            )
        usage = self._usage(payload)
        cost = self._cost(usage) if usage.reported else None
        response_model = str(payload.get("model") or self._settings.model)
        served_tier = str(payload.get("service_tier") or self._settings.service_tier)
        metadata = self.metadata.model_copy(
            update={"model_version": response_model, "service_tier": served_tier}
        )
        if payload.get("status") != "completed":
            detail = payload.get("incomplete_details")
            reason = detail.get("reason") if isinstance(detail, dict) else None
            return self._failure(
                started,
                ProviderOutcome.PROVIDER_FAILURE,
                f"incomplete:{reason or 'unknown'}",
                usage=usage,
                estimated_cost_usd=cost,
                metadata=metadata,
            )
        text = _output_text(payload)
        if text is None:
            refused = any(
                isinstance(content, dict) and content.get("type") == "refusal"
                for item in payload.get("output", []) if isinstance(item, dict)
                for content in item.get("content", [])
            )
            return self._failure(
                started,
                (
                    ProviderOutcome.PROVIDER_REFUSAL
                    if refused
                    else ProviderOutcome.STRUCTURED_OUTPUT_FAILURE
                ),
                "model_refusal" if refused else "missing_output_text",
                usage=usage,
                estimated_cost_usd=cost,
                metadata=metadata,
            )
        try:
            prediction = ModelStructuredPrediction.model_validate_json(text)
        except ValidationError as exc:
            return self._failure(
                started,
                ProviderOutcome.STRUCTURED_OUTPUT_FAILURE,
                "structured_output_validation",
                usage=usage,
                estimated_cost_usd=cost,
                metadata=metadata,
                validation_errors=validation_issues_from_error(
                    exc, stage=ValidationStage.STRUCTURED_OUTPUT
                ),
            )
        domain_errors = validate_prediction_domain(prediction)
        if domain_errors:
            return self._failure(
                started,
                ProviderOutcome.DOMAIN_VALIDATION_FAILURE,
                "domain_validation",
                usage=usage,
                estimated_cost_usd=cost,
                metadata=metadata,
                validation_errors=domain_errors,
            )
        if prediction.abstain:
            return self._failure(
                started,
                ProviderOutcome.MODEL_ABSTENTION,
                "model_abstention",
                usage=usage,
                estimated_cost_usd=cost,
                metadata=metadata,
            )
        return ProviderResult(
            status=coarse_status_for_outcome(ProviderOutcome.VALID_PREDICTION),
            outcome=ProviderOutcome.VALID_PREDICTION,
            prediction=prediction,
            metadata=metadata,
            latency_ms=(perf_counter() - started) * 1000,
            usage=usage,
            estimated_cost_usd=cost,
        )

    def _failure(
        self,
        started: float,
        outcome: ProviderOutcome,
        code: str,
        *,
        usage: TokenUsage | None = None,
        estimated_cost_usd: float | None = None,
        metadata: ProviderMetadata | None = None,
        validation_errors: list[ValidationIssue] | None = None,
    ) -> ProviderResult:
        return ProviderResult(
            status=coarse_status_for_outcome(outcome),
            outcome=outcome,
            metadata=metadata or self.metadata,
            latency_ms=(perf_counter() - started) * 1000,
            usage=usage or TokenUsage(),
            estimated_cost_usd=estimated_cost_usd,
            error_code=code,
            validation_errors=validation_errors or [],
        )

    @staticmethod
    def _usage(payload: dict[str, Any]) -> TokenUsage:
        reported = isinstance(payload.get("usage"), dict)
        usage = payload.get("usage") if reported else {}
        input_details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}
        return TokenUsage(
            input_tokens=int(usage.get("input_tokens") or 0),
            cached_input_tokens=int(input_details.get("cached_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            reasoning_tokens=int(output_details.get("reasoning_tokens") or 0),
            reported=reported,
        )

    @staticmethod
    def _cost(usage: TokenUsage) -> float:
        uncached = max(0, usage.input_tokens - usage.cached_input_tokens)
        return (
            uncached * INPUT_USD_PER_MILLION
            + usage.cached_input_tokens * CACHED_INPUT_USD_PER_MILLION
            + usage.output_tokens * OUTPUT_USD_PER_MILLION
        ) / 1_000_000
