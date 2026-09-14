"""CLI entry point for the offline synthetic classifier benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.dataset import DATA_DIRECTORY, DatasetError, load_cases, load_manifest
from evaluation.metrics import evaluate
from evaluation.pipeline import predict_cases
from evaluation.schemas import BinaryMetrics, EvaluationCase, EvaluationReport


def _metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _binary_line(name: str, metric: BinaryMetrics) -> str:
    label = name.replace("_", " ").title()
    return (
        f"{label:<28} P={_metric(metric.precision)} "
        f"R={_metric(metric.recall)} F1={_metric(metric.f1)} "
        f"TP={metric.tp} FP={metric.fp} FN={metric.fn}"
    )


def _tag_error_score(report: EvaluationReport, tag: str) -> int:
    metrics = report.by_tag[tag]
    binary_errors = sum(
        metric.fp + metric.fn for metric in metrics.binary_metrics.values()
    )
    return binary_errors + metrics.cases - metrics.route_correct


def render_console(
    report: EvaluationReport,
    cases: list[EvaluationCase],
    *,
    verbose: bool = False,
    max_failures: int = 20,
) -> str:
    lines = [
        f"{report.baseline_id} — {report.dataset_version}",
        f"Split: {report.split} | Cases: {report.case_count} | "
        f"Fingerprint: {report.dataset_fingerprint[:12]}",
        "",
        "CORE METRICS",
    ]
    for name, metric in report.binary_metrics.items():
        lines.append(_binary_line(name, metric))

    dates = report.date_metrics
    lines.extend(
        [
            "",
            "DATE EXTRACTION",
            f"Extraction precision: {_metric(dates.extraction_precision)}",
            f"Extraction recall:    {_metric(dates.extraction_recall)}",
            f"Exact normalized:     {_metric(dates.exact_normalized_match_rate)} "
            f"({dates.exact_normalized_match_count}/{dates.expected_count})",
            f"Time tolerance:       {_metric(dates.time_tolerance_accuracy)} "
            f"({dates.time_tolerance_match_count}/{dates.timed_expected_count}, "
            f"±{dates.tolerance_minutes}m)",
            "",
            "ABSTENTION / ROUTING",
            f"Route accuracy:       {_metric(report.route_accuracy)}",
            f"Coverage:             {_metric(report.abstention.coverage)}",
            "Accepted error rate:  "
            f"{_metric(report.abstention.error_rate_among_accepted)}",
            "",
            "PROTECTED ERROR COUNTS",
            "False required actions:          "
            f"{report.protected_metrics.false_required_action_count} "
            f"(rate={_metric(report.protected_metrics.false_required_action_rate)})",
            "Required-action false negatives: "
            f"{report.protected_metrics.required_action_false_negative_count}",
            "Upcoming-event false negatives:  "
            f"{report.protected_metrics.upcoming_event_false_negative_count}",
            "Deadline false negatives:        "
            f"{report.protected_metrics.deadline_false_negative_count}",
            "",
            "ROUTE CONFUSION (expected -> predicted nonzero counts)",
        ]
    )
    for expected, row in report.route_confusion.items():
        observed = ", ".join(
            f"{predicted}={count}" for predicted, count in row.items() if count
        )
        lines.append(f"{expected:<18} {observed or '(none)'}")

    lines.extend(["", "TOP TAG ERROR CATEGORIES"])
    ranked_tags = sorted(
        report.by_tag,
        key=lambda tag: (-_tag_error_score(report, tag), tag),
    )
    for tag in ranked_tags[:10]:
        metrics = report.by_tag[tag]
        lines.append(
            f"{tag:<22} errors={_tag_error_score(report, tag)} "
            f"cases={metrics.cases} route_accuracy={_metric(metrics.route_accuracy)}"
        )

    lines.extend(["", f"FAILURES (showing up to {max_failures})"])
    by_id = {case.id: case for case in cases}
    for failure in report.failures[:max_failures]:
        lines.append(f"CASE: {failure.id}")
        lines.append(f"TAGS: {', '.join(failure.tags)}")
        lines.append(f"Expected: {json.dumps(failure.expected, sort_keys=True)}")
        lines.append(f"Predicted: {json.dumps(failure.predicted, sort_keys=True)}")
        if verbose:
            case = by_id[failure.id]
            lines.append(f"Synthetic subject: {case.input.subject}")
            lines.append(f"Synthetic body: {case.input.body}")
        lines.append("")
    if len(report.failures) > max_failures:
        lines.append(f"{len(report.failures) - max_failures} additional failures omitted.")
    if not report.failures:
        lines.append("None")
    return "\n".join(lines).rstrip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.run",
        description=(
            "Run the production deterministic classifier against committed "
            "synthetic fixtures only. No Gmail or network access is used."
        ),
    )
    parser.add_argument("--dataset", choices=("v1", "v2"), default="v1")
    parser.add_argument("--split", default="all")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--output", type=Path, help="Write machine-readable JSON to a file")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include synthetic fixture text in console failure details",
    )
    parser.add_argument("--max-failures", type=int, default=20)
    parser.add_argument("--time-tolerance-minutes", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_failures < 0 or args.time_tolerance_minutes < 0:
        raise SystemExit("failure and tolerance values must be non-negative")
    try:
        manifest_path = (
            DATA_DIRECTORY / "manifest.json"
            if args.dataset == "v1"
            else DATA_DIRECTORY / "manifest_v2.json"
        )
        declared = load_manifest(manifest_path)
        if args.split not in {"all", *declared.split_order}:
            raise DatasetError(f"unknown evaluation split: {args.split}")
        manifest, cases, split_counts = load_cases(
            args.split, manifest_path=manifest_path
        )
    except DatasetError as exc:
        raise SystemExit(str(exc)) from exc
    predictions = predict_cases(cases, timezone_name=manifest.default_timezone)
    report = evaluate(
        cases,
        predictions,
        dataset_version=manifest.dataset_version,
        split=args.split,
        split_counts=split_counts,
        tolerance_minutes=args.time_tolerance_minutes,
        baseline_id=(
            "deterministic-baseline-v1"
            if args.dataset == "v1"
            else "unchanged-deterministic-classifier-v2"
        ),
    )
    serialized = report.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{serialized}\n", encoding="utf-8")
    if args.json:
        print(serialized)
    else:
        print(
            render_console(
                report,
                cases,
                verbose=args.verbose,
                max_failures=args.max_failures,
            )
        )
        if args.output:
            print(f"\nMachine-readable report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
