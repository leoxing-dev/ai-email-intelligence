"""Build hybrid-v1 snapshots from frozen model-only results and rules-v2."""

from __future__ import annotations

from datetime import UTC, datetime

from app.ai.hybrid import HYBRID_POLICY_VERSION, combine_predictions
from evaluation.dataset import dataset_fingerprint
from evaluation.metrics import evaluate
from evaluation.model_pipeline import _telemetry
from evaluation.model_schemas import (
    HybridDiagnostics,
    ModelCaseResult,
    ModelExperimentSnapshot,
)
from evaluation.schemas import EvaluationCase, EvaluationReport


def run_hybrid_experiment(
    cases: list[EvaluationCase],
    *,
    model_snapshot: ModelExperimentSnapshot,
    rules_report: EvaluationReport,
    timezone_name: str,
    dataset_version: str,
    split: str,
    split_counts: dict[str, int],
) -> ModelExperimentSnapshot:
    if model_snapshot.experiment_id != "model-only-v1":
        raise ValueError("hybrid requires a model-only-v1 snapshot")
    if model_snapshot.dataset_fingerprint != dataset_fingerprint(cases):
        raise ValueError("model snapshot does not match the selected dataset")
    if rules_report.baseline_id != "deterministic-rules-v2":
        raise ValueError("hybrid requires a deterministic-rules-v2 snapshot")
    if rules_report.dataset_fingerprint != dataset_fingerprint(cases):
        raise ValueError("rules snapshot does not match the selected dataset")

    rule_predictions = rules_report.predictions
    model_by_id = {item.case_id: item for item in model_snapshot.cases}
    if {item.id for item in rule_predictions} != set(model_by_id):
        raise ValueError("rules and model snapshots must contain identical case IDs")
    hybrid_results: list[ModelCaseResult] = []
    for rules in rule_predictions:
        model_result = model_by_id[rules.id]
        decision = combine_predictions(rules, model_result)
        hybrid_results.append(
            model_result.model_copy(
                update={
                    "prediction": decision.prediction,
                    "confidence": decision.confidence,
                    "error_code": model_result.error_code,
                    "hybrid_diagnostics": HybridDiagnostics(
                        deterministic_route=rules.route.value,
                        model_route=model_result.prediction.route.value,
                        final_route=decision.prediction.route.value,
                        field_sources=decision.field_sources,
                        disagreements=list(decision.disagreements),
                        policy_decisions=list(decision.policy_decisions),
                        abstained_for_conflict=decision.abstained_for_conflict,
                    ),
                }
            )
        )
    predictions = [item.prediction for item in hybrid_results]
    report = evaluate(
        cases,
        predictions,
        dataset_version=dataset_version,
        split=split,
        split_counts=split_counts,
        baseline_id="hybrid-v1",
    )
    return ModelExperimentSnapshot(
        experiment_id="hybrid-v1",
        created_at=datetime.now(UTC),
        dataset_version=dataset_version,
        dataset_fingerprint=dataset_fingerprint(cases),
        split=split,
        provider=model_snapshot.provider,
        hybrid_policy_version=HYBRID_POLICY_VERSION,
        report=report,
        telemetry=_telemetry(cases, hybrid_results, provider_calls=False),
        cases=hybrid_results,
    )
