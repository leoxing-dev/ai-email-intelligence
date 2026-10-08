"""CLI for opt-in synthetic-only model and hybrid evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.ai.base import ModelConfigurationError
from app.ai.config import ModelSettings
from app.ai.providers.openai import OpenAIModelExtractor
from evaluation.dataset import DATA_DIRECTORY, DatasetError, load_cases
from evaluation.hybrid_pipeline import run_hybrid_experiment
from evaluation.model_pipeline import run_model_experiment
from evaluation.model_schemas import ModelExperimentSnapshot
from evaluation.schemas import EvaluationReport
from evaluation.run import render_console


def _load_snapshot(path: Path) -> ModelExperimentSnapshot:
    try:
        return ModelExperimentSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not load model snapshot: {path.name}") from exc


def _load_report(path: Path) -> EvaluationReport:
    try:
        return EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not load rules snapshot: {path.name}") from exc


def _write_snapshot(path: Path, snapshot: ModelExperimentSnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")


def _print_summary(snapshot: ModelExperimentSnapshot, cases) -> None:
    print(
        "END-TO-END QUALITY (unusable outcomes are evaluated as manual_review abstentions)"
    )
    print(render_console(snapshot.report, cases, max_failures=0))
    if snapshot.usable_report is not None:
        usable_ids = {item.id for item in snapshot.usable_report.predictions}
        usable_cases = [case for case in cases if case.id in usable_ids]
        print("\nSEMANTIC QUALITY (usable predictions only)")
        print(render_console(snapshot.usable_report, usable_cases, max_failures=0))
    telemetry = snapshot.telemetry
    print("\nTECHNICAL RELIABILITY")
    print(
        f"external_requests={telemetry.external_request_count} "
        f"reused_predictions={telemetry.reused_prediction_count}"
    )
    print(
        f"valid={telemetry.valid_count} abstained={telemetry.abstention_count} "
        f"malformed={telemetry.malformed_count} failures={telemetry.provider_failure_count}"
    )
    print(
        f"request_success={telemetry.request_success_count}/{telemetry.total_cases} "
        f"rate={telemetry.request_success_rate}"
    )
    print(
        "structured_output_success="
        f"{telemetry.structured_output_success_count}/{telemetry.request_success_count} "
        f"rate={telemetry.structured_output_success_rate}"
    )
    print(
        "domain_validation_success="
        f"{telemetry.domain_validation_success_count}/"
        f"{telemetry.structured_output_success_count} "
        f"rate={telemetry.domain_validation_success_rate}"
    )
    print(
        f"usable_predictions={telemetry.usable_prediction_count}/"
        f"{telemetry.total_cases} rate={telemetry.usable_prediction_rate}"
    )
    print(
        "outcomes="
        + ",".join(
            f"{name}:{count}" for name, count in telemetry.outcome_counts.items()
        )
    )
    print(
        f"latency_ms avg={telemetry.average_latency_ms} "
        f"p50={telemetry.p50_latency_ms} p95={telemetry.p95_latency_ms}"
    )
    print(
        f"tokens/email input={telemetry.average_input_tokens} "
        f"output={telemetry.average_output_tokens} total={telemetry.average_total_tokens}"
    )
    print(
        f"billable_attempts={telemetry.billable_attempt_count} "
        f"tokens input={telemetry.total_input_tokens} "
        f"output={telemetry.total_output_tokens} total={telemetry.total_tokens}"
    )
    print(
        f"estimated_total_cost_usd={telemetry.estimated_total_cost_usd} "
        f"complete={telemetry.cost_accounting_complete}"
    )
    print(f"estimated_cost_per_1000_usd={telemetry.estimated_cost_per_1000_emails_usd}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.model_run",
        description="Synthetic benchmark only; never accepts Gmail messages.",
    )
    parser.add_argument("--mode", choices=("model-only", "hybrid"), required=True)
    parser.add_argument("--split", choices=("v2_dev", "v2_test", "challenge"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-snapshot", type=Path)
    parser.add_argument("--rules-snapshot", type=Path)
    parser.add_argument(
        "--limit",
        type=int,
        help="Development smoke-test limit; permitted only for v2_dev",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and (args.limit < 1 or args.split != "v2_dev"):
        raise SystemExit("--limit is positive and permitted only for v2_dev")
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    try:
        manifest, cases, split_counts = load_cases(args.split, manifest_path=manifest_path)
    except DatasetError as exc:
        raise SystemExit(str(exc)) from exc
    if args.limit is not None:
        cases = cases[: args.limit]
        split_counts = {args.split: len(cases)}

    if args.mode == "model-only":
        if args.model_snapshot is not None or args.rules_snapshot is not None:
            raise SystemExit("snapshot inputs are valid only for hybrid mode")
        settings = ModelSettings()
        if settings.provider == "disabled":
            raise SystemExit(
                "model provider is disabled; set GMAIL_ASSISTANT_MODEL_PROVIDER=openai"
            )
        try:
            extractor = OpenAIModelExtractor(settings)
        except ModelConfigurationError as exc:
            raise SystemExit(str(exc)) from exc
        snapshot = run_model_experiment(
            cases,
            extractor=extractor,
            timezone_name=manifest.default_timezone,
            dataset_version=manifest.dataset_version,
            split=args.split,
            split_counts=split_counts,
            max_workers=settings.max_workers,
        )
    else:
        if args.model_snapshot is None:
            raise SystemExit("hybrid mode requires --model-snapshot")
        if args.rules_snapshot is None:
            raise SystemExit("hybrid mode requires --rules-snapshot")
        model_snapshot = _load_snapshot(args.model_snapshot)
        rules_report = _load_report(args.rules_snapshot)
        snapshot = run_hybrid_experiment(
            cases,
            model_snapshot=model_snapshot,
            rules_report=rules_report,
            timezone_name=manifest.default_timezone,
            dataset_version=manifest.dataset_version,
            split=args.split,
            split_counts=split_counts,
        )

    _write_snapshot(args.output, snapshot)
    _print_summary(snapshot, cases)
    if snapshot.telemetry.provider_failure_count or snapshot.telemetry.malformed_count:
        codes = sorted({item.error_code for item in snapshot.cases if item.error_code})
        print("Provider errors: " + ", ".join(codes))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
