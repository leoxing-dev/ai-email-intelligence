"""Deterministic fake provider for offline unit tests."""

from __future__ import annotations

from collections import deque
import json
from typing import Any

from pydantic import ValidationError

from app.ai.base import ModelExtractor
from app.ai.schemas import (
    ModelStructuredPrediction,
    ProviderMetadata,
    ProviderOutcome,
    ProviderResult,
    SyntheticEmailRecord,
    TokenUsage,
    coarse_status_for_outcome,
    validate_prediction_domain,
    validation_issues_from_error,
    ValidationStage,
)
from app.ai.prompts.model_only_v1 import PROMPT_VERSION


class FakeModelExtractor(ModelExtractor):
    """Return queued payloads without network, credentials, or model access."""

    def __init__(self, responses: list[dict[str, Any] | Exception], *, latency_ms: float = 7.0):
        self._responses = deque(responses)
        self._latency_ms = latency_ms
        self.seen_case_ids: list[str] = []

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider="fake",
            model="fake-structured-model",
            model_version="test-only-v1",
            reasoning_effort=None,
            service_tier=None,
            prompt_version=PROMPT_VERSION,
        )

    def extract(self, record: SyntheticEmailRecord) -> ProviderResult:
        self.seen_case_ids.append(record.case_id)
        if not self._responses:
            item: dict[str, Any] | Exception = RuntimeError("fake response queue exhausted")
        else:
            item = self._responses.popleft()
        if isinstance(item, TimeoutError):
            return self._result(ProviderOutcome.PROVIDER_FAILURE, error_code="timeout")
        if isinstance(item, Exception):
            return self._result(
                ProviderOutcome.PROVIDER_FAILURE, error_code="provider_error"
            )
        usage = TokenUsage(input_tokens=100, output_tokens=40, reported=True)
        try:
            prediction = ModelStructuredPrediction.model_validate_json(json.dumps(item))
        except ValidationError as exc:
            return self._result(
                ProviderOutcome.STRUCTURED_OUTPUT_FAILURE,
                error_code="structured_output_validation",
                usage=usage,
                validation_errors=validation_issues_from_error(
                    exc, stage=ValidationStage.STRUCTURED_OUTPUT
                ),
            )
        domain_errors = validate_prediction_domain(prediction)
        if domain_errors:
            return self._result(
                ProviderOutcome.DOMAIN_VALIDATION_FAILURE,
                error_code="domain_validation",
                usage=usage,
                validation_errors=domain_errors,
            )
        if prediction.abstain:
            return self._result(
                ProviderOutcome.MODEL_ABSTENTION,
                error_code="model_abstention",
                usage=usage,
            )
        return ProviderResult(
            status=coarse_status_for_outcome(ProviderOutcome.VALID_PREDICTION),
            outcome=ProviderOutcome.VALID_PREDICTION,
            prediction=prediction,
            metadata=self.metadata,
            latency_ms=self._latency_ms,
            usage=usage,
            estimated_cost_usd=0.00068,
        )

    def _result(
        self,
        outcome: ProviderOutcome,
        *,
        error_code: str,
        usage: TokenUsage | None = None,
        validation_errors=None,
    ) -> ProviderResult:
        usage = usage or TokenUsage()
        return ProviderResult(
            status=coarse_status_for_outcome(outcome),
            outcome=outcome,
            metadata=self.metadata,
            latency_ms=self._latency_ms,
            usage=usage,
            estimated_cost_usd=0.00068 if usage.reported else None,
            error_code=error_code,
            validation_errors=validation_errors or [],
        )
