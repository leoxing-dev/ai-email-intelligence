"""One-time V3 orchestration around the already frozen evaluation systems."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.ai.base import ModelConfigurationError
from app.ai.config import ModelSettings
from app.ai.hybrid import HYBRID_POLICY_VERSION
from app.ai.prompts.model_only_v1 import PROMPT_VERSION
from app.ai.providers.openai import OpenAIModelExtractor
from evaluation.dataset import DATA_DIRECTORY, load_cases
from evaluation.hybrid_pipeline import run_hybrid_experiment
from evaluation.metrics import evaluate
from evaluation.model_pipeline import run_model_experiment
from evaluation.model_run import _load_report, _load_snapshot, _write_snapshot
from evaluation.pipeline import predict_cases


MANIFEST = DATA_DIRECTORY / "manifest_v3.json"
EXPECTED_DATASET = "synthetic-email-benchmark-v3-blind"


def _new_output(path: Path) -> None:
    if path.exists():
        raise SystemExit(f"refusing to overwrite one-time V3 artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)


def _cases(split: str):
    manifest, cases, counts = load_cases(split, manifest_path=MANIFEST)
    if manifest.dataset_version != EXPECTED_DATASET:
        raise SystemExit("unexpected V3 dataset version")
    return manifest, cases, counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen one-time V3 evaluation")
    parser.add_argument(
        "--mode", choices=("deterministic", "model-only", "hybrid"), required=True
    )
    parser.add_argument(
        "--split", choices=("v3_test", "v3_challenge"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-snapshot", type=Path)
    parser.add_argument("--rules-snapshot", type=Path)
    args = parser.parse_args()
    _new_output(args.output)
    manifest, cases, counts = _cases(args.split)

    if args.mode == "deterministic":
        if args.model_snapshot or args.rules_snapshot:
            raise SystemExit("deterministic mode does not accept snapshots")
        predictions = predict_cases(cases, timezone_name=manifest.default_timezone)
        report = evaluate(
            cases,
            predictions,
            dataset_version=manifest.dataset_version,
            split=args.split,
            split_counts=counts,
            baseline_id="deterministic-rules-v2",
        )
        args.output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return 0

    if args.mode == "model-only":
        if args.model_snapshot or args.rules_snapshot:
            raise SystemExit("model-only mode does not accept snapshots")
        settings = ModelSettings()
        expected = ("openai", "gpt-5.6-terra", "medium", "default")
        actual = (
            settings.provider,
            settings.model,
            settings.reasoning_effort,
            settings.service_tier,
        )
        if actual != expected or PROMPT_VERSION != "model-only-v1-prompt-1":
            raise SystemExit("frozen model configuration mismatch")
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
            split_counts=counts,
            max_workers=settings.max_workers,
        )
        _write_snapshot(args.output, snapshot)
        return 2 if (
            snapshot.telemetry.provider_failure_count
            or snapshot.telemetry.malformed_count
        ) else 0

    if not args.model_snapshot or not args.rules_snapshot:
        raise SystemExit("hybrid mode requires model and rules snapshots")
    if HYBRID_POLICY_VERSION != "hybrid-v1-policy-1":
        raise SystemExit("frozen hybrid policy mismatch")
    snapshot = run_hybrid_experiment(
        cases,
        model_snapshot=_load_snapshot(args.model_snapshot),
        rules_report=_load_report(args.rules_snapshot),
        timezone_name=manifest.default_timezone,
        dataset_version=manifest.dataset_version,
        split=args.split,
        split_counts=counts,
    )
    _write_snapshot(args.output, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
