"""Privacy-minimized schemas for model and hybrid benchmark snapshots."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ai.schemas import (
    ProviderMetadata,
    ProviderOutcome,
    ProviderStatus,
    TokenUsage,
    ValidationIssue,
    infer_outcome,
)
from evaluation.schemas import CasePrediction, EvaluationReport


class HybridDiagnostics(BaseModel):
    """Privacy-safe provenance for a hybrid semantic decision."""

    model_config = ConfigDict(extra="forbid")

    deterministic_route: str
    model_route: str
    final_route: str
    field_sources: dict[str, str] = Field(default_factory=dict)
    disagreements: list[str] = Field(default_factory=list)
    policy_decisions: list[str] = Field(default_factory=list)
    abstained_for_conflict: bool = False


class ModelCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    status: ProviderStatus
    outcome: ProviderOutcome | None = None
    prediction: CasePrediction
    confidence: float = Field(ge=0, le=1)
    latency_ms: float = Field(ge=0)
    usage: TokenUsage
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    hybrid_diagnostics: HybridDiagnostics | None = None

    @model_validator(mode="after")
    def load_legacy_outcome(self) -> "ModelCaseResult":
        if self.outcome is None:
            self.outcome = infer_outcome(self.status, self.error_code)
        return self


class ConfidencePrecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold: float
    predicted_positive: int
    true_positive: int
    false_positive: int
    precision: float | None


class ExperimentTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cases: int
    external_request_count: int = 0
    reused_prediction_count: int = 0
    valid_count: int
    abstention_count: int
    malformed_count: int
    provider_failure_count: int
    outcome_counts: dict[str, int] = Field(default_factory=dict)
    request_success_count: int = 0
    request_success_rate: float | None = None
    structured_output_success_count: int = 0
    structured_output_success_rate: float | None = None
    domain_validation_success_count: int = 0
    domain_validation_success_rate: float | None = None
    usable_prediction_count: int = 0
    usable_prediction_rate: float | None = None
    billable_attempt_count: int = 0
    average_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    average_input_tokens: float | None
    average_output_tokens: float | None
    average_total_tokens: float | None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_reasoning_tokens: int = 0
    estimated_total_cost_usd: float | None
    estimated_cost_per_1000_emails_usd: float | None
    cost_accounting_complete: bool = False
    required_action_precision_by_confidence: list[ConfidencePrecision]


class ModelExperimentSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    created_at: datetime
    dataset_version: str
    dataset_fingerprint: str
    split: str
    provider: ProviderMetadata
    hybrid_policy_version: str | None = None
    usable_report: EvaluationReport | None = None
    report: EvaluationReport
    telemetry: ExperimentTelemetry
    cases: list[ModelCaseResult]
