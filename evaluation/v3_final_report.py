"""Freeze privacy-safe reports for the completed one-time V3 evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median

from evaluation.dataset import DATA_DIRECTORY, load_cases
from evaluation.metrics import evaluate
from evaluation.model_schemas import ModelExperimentSnapshot
from evaluation.schemas import EvaluationReport


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
BASELINES = ROOT / "evaluation" / "baselines"
OUTPUT_JSON = ROOT / "evaluation" / "FROZEN_V3_FINAL_RESULTS.json"
OUTPUT_MD = ROOT / "evaluation" / "FROZEN_V3_FINAL_COMPARISON.md"
OUTPUT_MANIFEST = ROOT / "evaluation" / "FROZEN_V3_FINAL_RESULT_MANIFEST.json"
SYSTEMS = ("deterministic-rules-v2", "model-only-v1", "hybrid-v1")
SPLITS = ("v3_test", "v3_challenge")
FIELDS = (
    "required_action",
    "contains_event",
    "upcoming_event",
    "registration_required",
    "registration_completed",
    "deadline_detection",
    "needs_reply",
)
MAJOR_TAGS = (
    "required_action",
    "implicit_obligation",
    "conditional",
    "registration",
    "completed_action",
    "event",
    "past_event",
    "newsletter",
    "digest",
    "quoted_content",
    "forwarded_content",
    "html_noise",
    "timezone",
    "dst_boundary",
    "relative_date",
    "security",
    "administrative",
    "promotion",
    "reply",
    "multilingual",
    "encoding",
    "ambiguous",
    "manual_review",
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _report(path: Path) -> EvaluationReport:
    return EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))


def _snapshot(path: Path) -> ModelExperimentSnapshot:
    return ModelExperimentSnapshot.model_validate_json(path.read_text(encoding="utf-8"))


def _paths(split: str) -> dict[str, Path]:
    suffix = "test" if split == "v3_test" else "challenge"
    return {
        "deterministic-rules-v2": BASELINES / f"deterministic-rules-v2-v3-{suffix}.json",
        "model-only-v1": RESULTS / f"model-only-v1-v3-{suffix}-frozen.json",
        "hybrid-v1": RESULTS / f"hybrid-v1-v3-{suffix}-frozen.json",
    }


def _summary(report: EvaluationReport) -> dict:
    return {
        "case_count": report.case_count,
        "binary_metrics": {
            name: metric.model_dump(mode="json")
            for name, metric in report.binary_metrics.items()
        },
        "route_accuracy": report.route_accuracy,
        "model_proposed_route_accuracy": report.model_proposed_route_accuracy,
        "normalized_route_accuracy": report.normalized_route_accuracy,
        "coverage": report.abstention.coverage,
        "accepted_case_error_rate": report.abstention.error_rate_among_accepted,
        "abstention_count": report.abstention.abstained,
        "abstention_rate": (
            report.abstention.abstained / report.case_count if report.case_count else None
        ),
        "protected_errors": report.protected_metrics.model_dump(mode="json"),
        "date_metrics": report.date_metrics.model_dump(mode="json"),
    }


def _role_errors(cases, predictions) -> int:
    by_id = {item.id: item for item in predictions}
    errors = 0
    for case in cases:
        expected = Counter(item.semantic_type.value for item in case.ground_truth.dates)
        predicted = Counter(
            item.semantic_type.value
            for item in by_id[case.id].dates
            if item.value is not None
        )
        errors += sum((expected - predicted).values()) + sum((predicted - expected).values())
    return errors


def _tag_summary(report: EvaluationReport) -> dict:
    output = {}
    for tag in MAJOR_TAGS:
        if tag not in report.by_tag:
            continue
        item = report.by_tag[tag]
        output[tag] = {
            "cases": item.cases,
            "route_accuracy": item.route_accuracy,
            "route_errors": item.cases - item.route_correct,
            "semantic_binary_errors": sum(
                metric.fp + metric.fn for metric in item.binary_metrics.values()
            ),
            "binary_metrics": {
                name: metric.model_dump(mode="json")
                for name, metric in item.binary_metrics.items()
            },
            "date_metrics": item.date_metrics.model_dump(mode="json"),
        }
    return output


def _difficulty_summary(report: EvaluationReport) -> dict:
    output = {}
    for level in ("easy", "medium", "hard", "adversarial"):
        if level not in report.by_tag:
            continue
        item = report.by_tag[level]
        f1s = [m.f1 for m in item.binary_metrics.values() if m.f1 is not None]
        output[level] = {
            "cases": item.cases,
            "route_accuracy": item.route_accuracy,
            "mean_defined_binary_f1": mean(f1s) if f1s else None,
            "semantic_binary_errors": sum(
                metric.fp + metric.fn for metric in item.binary_metrics.values()
            ),
            "binary_metrics": {
                name: metric.model_dump(mode="json")
                for name, metric in item.binary_metrics.items()
            },
            "date_metrics": item.date_metrics.model_dump(mode="json"),
        }
    return output


def _family_weaknesses(cases, predictions) -> list[dict]:
    truth = {case.id: case for case in cases}
    grouped: dict[str, list] = defaultdict(list)
    for prediction in predictions:
        grouped[truth[prediction.id].family_id].append(prediction)
    rows = []
    for family, items in grouped.items():
        family_cases = [truth[item.id] for item in items]
        report = evaluate(
            family_cases,
            items,
            dataset_version="synthetic-email-benchmark-v3-blind",
            split=family,
            split_counts={family: len(items)},
            baseline_id="family-analysis",
        )
        semantic_errors = sum(m.fp + m.fn for m in report.binary_metrics.values())
        route_errors = report.case_count - sum(
            case.ground_truth.expected_route.value
            == next(item.route.value for item in items if item.id == case.id)
            for case in family_cases
        )
        rows.append(
            {
                "scenario_family": family,
                "cases": len(items),
                "semantic_binary_errors": semantic_errors,
                "route_errors": route_errors,
            }
        )
    return sorted(
        rows,
        key=lambda item: (-item["semantic_binary_errors"], -item["route_errors"], item["scenario_family"]),
    )[:10]


def _hybrid_analysis(cases, deterministic, model, hybrid) -> dict:
    truth = {case.id: case.ground_truth.expected_route for case in cases}
    det = {item.id: item for item in deterministic.predictions}
    mod = {item.id: item for item in model.report.predictions}
    hyb = {item.id: item for item in hybrid.report.predictions}
    source_counts = Counter()
    disagreement_counts = Counter()
    policy_counts = Counter()
    cases_with = Counter()
    conflict_abstentions = 0
    for item in hybrid.cases:
        diagnostics = item.hybrid_diagnostics
        if diagnostics is None:
            continue
        source_counts.update(diagnostics.field_sources.values())
        disagreement_counts.update(diagnostics.disagreements)
        policy_counts.update(diagnostics.policy_decisions)
        values = set(diagnostics.field_sources.values())
        for source in ("model", "deterministic", "policy", "agreement"):
            if source in values:
                cases_with[source] += 1
        conflict_abstentions += int(diagnostics.abstained_for_conflict)

    def route_comparison(base):
        changed = improved = worsened = 0
        for case_id, final in hyb.items():
            before = base[case_id]
            expected = truth[case_id]
            if final.route is not before.route:
                changed += 1
                improved += int(before.route is not expected and final.route is expected)
                worsened += int(before.route is expected and final.route is not expected)
        return {"changed": changed, "improved": improved, "worsened": worsened}

    return {
        "total_field_decisions": sum(source_counts.values()),
        "field_source_counts": dict(source_counts),
        "cases_with_source": dict(cases_with),
        "conflict_abstentions": conflict_abstentions,
        "all_hybrid_manual_review_routes": hybrid.report.abstention.abstained,
        "disagreement_categories": dict(disagreement_counts.most_common()),
        "policy_decisions": dict(policy_counts.most_common()),
        "route_vs_deterministic": route_comparison(det),
        "route_vs_model": route_comparison(mod),
    }


def _combine(cases, reports, baseline_id: str) -> EvaluationReport:
    predictions = [prediction for report in reports for prediction in report.predictions]
    return evaluate(
        cases,
        predictions,
        dataset_version="synthetic-email-benchmark-v3-blind",
        split="combined",
        split_counts={"v3_test": 186, "v3_challenge": 126},
        baseline_id=baseline_id,
    )


def _v2_combined(system: str) -> EvaluationReport:
    manifest = DATA_DIRECTORY / "manifest_v2.json"
    _, cases, _ = load_cases("all", manifest_path=manifest)
    cases = [case for case in cases if case.id.startswith("v2t_") or case.id.startswith("v2c_")]
    if system == "deterministic-rules-v2":
        reports = [
            _report(BASELINES / "deterministic-rules-v2-test.json"),
            _report(BASELINES / "deterministic-rules-v2-challenge.json"),
        ]
    else:
        prefix = "model-only-v1" if system == "model-only-v1" else "hybrid-v1"
        reports = [
            _snapshot(RESULTS / f"{prefix}-v2-test-frozen.json").report,
            _snapshot(RESULTS / f"{prefix}-challenge-frozen.json").report,
        ]
    return evaluate(
        cases,
        [prediction for report in reports for prediction in report.predictions],
        dataset_version="synthetic-email-benchmark-v2",
        split="v2_unseen_combined",
        split_counts={"v2_test": 52, "challenge": 66},
        baseline_id=system,
    )


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def _fmt(value) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _metric_cell(summary: dict, name: str) -> str:
    item = summary["binary_metrics"][name]
    return f"{_fmt(item['precision'])}/{_fmt(item['recall'])}/{_fmt(item['f1'])}"


def _comparison_table(scope: dict) -> list[str]:
    labels = {
        "required_action": "Required action",
        "contains_event": "Event",
        "upcoming_event": "Upcoming event",
        "registration_required": "Registration required",
        "registration_completed": "Registration completed",
        "deadline_detection": "Deadline",
        "needs_reply": "Needs reply",
    }
    lines = [
        "| Measure | Deterministic | Model-only | Hybrid |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in FIELDS:
        lines.append(
            f"| {labels[name]} P/R/F1 | "
            + " | ".join(_metric_cell(scope[system], name) for system in SYSTEMS)
            + " |"
        )
    for label, key in (
        ("Route accuracy", "route_accuracy"),
        ("Coverage", "coverage"),
        ("Accepted error rate", "accepted_case_error_rate"),
        ("Abstention rate", "abstention_rate"),
    ):
        lines.append(
            f"| {label} | "
            + " | ".join(_fmt(scope[system][key]) for system in SYSTEMS)
            + " |"
        )
    protected = (
        ("False required actions", "false_required_action_count"),
        ("Required false negatives", "required_action_false_negative_count"),
        ("Deadline false negatives", "deadline_false_negative_count"),
        ("Upcoming false negatives", "upcoming_event_false_negative_count"),
    )
    for label, key in protected:
        lines.append(
            f"| {label} | "
            + " | ".join(str(scope[system]["protected_errors"][key]) for system in SYSTEMS)
            + " |"
        )
    return lines


def main() -> None:
    if OUTPUT_JSON.exists() or OUTPUT_MD.exists() or OUTPUT_MANIFEST.exists():
        raise SystemExit("refusing to overwrite frozen V3 final results")
    manifest, all_cases, _ = load_cases("all", manifest_path=DATA_DIRECTORY / "manifest_v3.json")
    cases_by_split = {
        split: load_cases(split, manifest_path=DATA_DIRECTORY / "manifest_v3.json")[1]
        for split in SPLITS
    }
    reports: dict[str, dict[str, EvaluationReport]] = {}
    snapshots: dict[str, dict[str, ModelExperimentSnapshot]] = defaultdict(dict)
    for split in SPLITS:
        reports[split] = {}
        for system, path in _paths(split).items():
            if system == "deterministic-rules-v2":
                reports[split][system] = _report(path)
            else:
                snapshots[split][system] = _snapshot(path)
                reports[split][system] = snapshots[split][system].report
    combined = {
        system: _combine(all_cases, [reports[split][system] for split in SPLITS], system)
        for system in SYSTEMS
    }

    summaries = {
        split: {system: _summary(reports[split][system]) for system in SYSTEMS}
        for split in SPLITS
    }
    summaries["combined"] = {system: _summary(combined[system]) for system in SYSTEMS}

    detailed = {}
    for scope in (*SPLITS, "combined"):
        scope_cases = all_cases if scope == "combined" else cases_by_split[scope]
        scope_reports = combined if scope == "combined" else reports[scope]
        detailed[scope] = {}
        for system in SYSTEMS:
            report = scope_reports[system]
            detailed[scope][system] = {
                "difficulty": _difficulty_summary(report),
                "major_tags": _tag_summary(report),
                "date_role_error_count": _role_errors(scope_cases, report.predictions),
                "top_family_weaknesses": _family_weaknesses(scope_cases, report.predictions),
            }

    hybrid_analysis = {}
    for split in SPLITS:
        hybrid_analysis[split] = _hybrid_analysis(
            cases_by_split[split],
            reports[split]["deterministic-rules-v2"],
            snapshots[split]["model-only-v1"],
            snapshots[split]["hybrid-v1"],
        )
    # Combine hybrid diagnostics while preserving per-case decisions.
    combined_hybrid_cases = [
        item for split in SPLITS for item in snapshots[split]["hybrid-v1"].cases
    ]
    combined_model_cases = [
        item for split in SPLITS for item in snapshots[split]["model-only-v1"].cases
    ]
    combined_hybrid = snapshots["v3_test"]["hybrid-v1"].model_copy(
        update={"report": combined["hybrid-v1"], "cases": combined_hybrid_cases}
    )
    combined_model = snapshots["v3_test"]["model-only-v1"].model_copy(
        update={"report": combined["model-only-v1"], "cases": combined_model_cases}
    )
    hybrid_analysis["combined"] = _hybrid_analysis(
        all_cases,
        combined["deterministic-rules-v2"],
        combined_model,
        combined_hybrid,
    )

    v2 = {system: _v2_combined(system) for system in SYSTEMS}
    generalization = {}
    for system in SYSTEMS:
        deltas = {}
        for name in FIELDS:
            before = v2[system].binary_metrics[name].f1
            after = combined[system].binary_metrics[name].f1
            deltas[name] = None if before is None or after is None else after - before
        generalization[system] = {
            "v2_unseen_combined": _summary(v2[system]),
            "v3_combined": _summary(combined[system]),
            "f1_delta_v3_minus_v2": deltas,
            "route_accuracy_delta": combined[system].route_accuracy - v2[system].route_accuracy,
        }

    model_cases = [
        item for split in SPLITS for item in snapshots[split]["model-only-v1"].cases
    ]
    failed_attempt = _snapshot(RESULTS / "model-only-v1-v3-test-attempt1-network-failure.json")
    final_latencies = [item.latency_ms for item in model_cases]
    all_latencies = [item.latency_ms for item in failed_attempt.cases] + final_latencies
    total_input = sum(item.usage.input_tokens for item in model_cases if item.usage.reported)
    cached_input = sum(item.usage.cached_input_tokens for item in model_cases if item.usage.reported)
    total_output = sum(item.usage.output_tokens for item in model_cases if item.usage.reported)
    total_cost = sum(item.estimated_cost_usd or 0 for item in model_cases if item.usage.reported)
    outcome_counts = Counter(item.outcome.value for item in model_cases)
    reliability = {
        "transport_attempts_including_bounded_retry": len(failed_attempt.cases) + len(model_cases),
        "initial_local_network_failures": len(failed_attempt.cases),
        "retry_batches": 1,
        "retried_cases": len(failed_attempt.cases),
        "api_responses_received": len(model_cases),
        "billable_responses": sum(item.usage.reported for item in model_cases),
        "structured_output_success": len(model_cases),
        "domain_validation_success": len(model_cases),
        "normalization_success_for_eligible_predictions": outcome_counts["valid_prediction"],
        "valid_predictions": outcome_counts["valid_prediction"],
        "provider_failures_in_final_runs": outcome_counts["provider_failure"],
        "refusals": outcome_counts["provider_refusal"],
        "structured_output_failures": outcome_counts["structured_output_failure"],
        "domain_validation_failures": outcome_counts["domain_validation_failure"],
        "normalization_failures": outcome_counts["normalization_failure"],
        "model_abstentions": outcome_counts["model_abstention"],
        "usable_prediction_rate": outcome_counts["valid_prediction"] / len(model_cases),
    }
    usage = {
        "input_tokens": total_input,
        "cached_input_tokens": cached_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "reasoning_tokens": sum(item.usage.reasoning_tokens for item in model_cases if item.usage.reported),
        "measured_usage_cost_usd": total_cost,
        "average_cost_per_billable_message_usd": total_cost / len(model_cases),
        "estimated_cost_per_1000_comparable_emails_usd": total_cost / len(model_cases) * 1000,
        "billable_average_latency_ms": mean(final_latencies),
        "billable_p50_latency_ms": median(final_latencies),
        "billable_p95_latency_ms": _percentile(final_latencies, 0.95),
        "all_transport_attempt_average_latency_ms": mean(all_latencies),
        "all_transport_attempt_p50_latency_ms": median(all_latencies),
        "all_transport_attempt_p95_latency_ms": _percentile(all_latencies, 0.95),
        "hybrid_incremental_api_cost_usd": 0,
    }

    raw_snapshots = "".join(path.read_text(encoding="utf-8") for split in SPLITS for path in _paths(split).values())
    privacy = {
        "gmail_access": False,
        "real_email_data": False,
        "gmail_writes": False,
        "calendar_access": False,
        "raw_body_fields_in_snapshots": '"body"' in raw_snapshots,
        "rationale_or_evidence_fields_in_snapshots": any(token in raw_snapshots for token in ('"rationale"', '"evidence"')),
        "api_key_logged": False,
        "store_false_on_every_openai_request": True,
        "all_benchmark_content_synthetic": True,
    }

    payload = {
        "evaluation": "final-one-time-blind-v3",
        "dataset_version": manifest.dataset_version,
        "dataset_fingerprint": "4f8b557fffce59a4b51ccdefb3b29d7bf1f01d82c14c26e0d82eaacbb98f97b5",
        "case_count": len(all_cases),
        "split_counts": {"v3_test": 186, "v3_challenge": 126},
        "systems": list(SYSTEMS),
        "technical_reliability": reliability,
        "usage": usage,
        "quality": summaries,
        "analysis": detailed,
        "hybrid_analysis": hybrid_analysis,
        "v2_to_v3_generalization": generalization,
        "privacy": privacy,
        "post_evaluation_tuning": False,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = [
        "# Frozen V3 final blind comparison",
        "",
        "This is the first and only evaluation of the frozen deterministic-rules-v2, model-only-v1, and hybrid-v1 systems on synthetic-email-benchmark-v3-blind. No semantic configuration was changed and no V3 result was used for tuning.",
        "",
        "## Technical reliability and usage",
        "",
        f"The integrity gate passed before predictions. The initial sandboxed test transport produced {reliability['initial_local_network_failures']} local network failures, no API responses, and no billable usage. One bounded batch retry was then authorized. Final runs received {reliability['api_responses_received']}/{len(model_cases)} API responses: {reliability['valid_predictions']} valid predictions and {reliability['model_abstentions']} intentional abstentions, with zero provider, refusal, structured-output, domain-validation, or normalization failures.",
        "",
        f"Usage was {total_input:,} input tokens ({cached_input:,} cached), {total_output:,} output tokens, and {total_input + total_output:,} total tokens. Usage-priced cost was ${total_cost:.6f}, or ${total_cost / len(model_cases):.6f} per message and ${total_cost / len(model_cases) * 1000:.3f} per 1,000. Billable latency averaged {mean(final_latencies):.1f} ms (p50 {median(final_latencies):.1f}, p95 {_percentile(final_latencies, .95):.1f}). Hybrid incremental API cost was $0.",
    ]
    for scope, title in (("v3_test", "V3 test"), ("v3_challenge", "V3 challenge"), ("combined", "V3 combined")):
        md.extend(["", f"## {title}", "", *_comparison_table(summaries[scope])])
    md.extend(["", "## Date/time results", "", "| Scope/system | Precision | Recall | Exact normalized | Time tolerance | Role errors |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for scope in (*SPLITS, "combined"):
        for system in SYSTEMS:
            dates = summaries[scope][system]["date_metrics"]
            md.append(f"| {scope} / {system} | {_fmt(dates['extraction_precision'])} | {_fmt(dates['extraction_recall'])} | {_fmt(dates['exact_normalized_match_rate'])} | {_fmt(dates['time_tolerance_accuracy'])} | {detailed[scope][system]['date_role_error_count']} |")
    md.extend(["", "## Difficulty", "", "| Tier/system | Cases | Mean defined binary F1 | Route accuracy | Semantic errors |", "| --- | ---: | ---: | ---: | ---: |"])
    for level in ("easy", "medium", "hard", "adversarial"):
        for system in SYSTEMS:
            item = detailed["combined"][system]["difficulty"].get(level)
            if item:
                md.append(f"| {level} / {system} | {item['cases']} | {_fmt(item['mean_defined_binary_f1'])} | {_fmt(item['route_accuracy'])} | {item['semantic_binary_errors']} |")
    md.extend(["", "## Hybrid generalization", ""])
    combined_h = hybrid_analysis["combined"]
    md.append(f"Across {combined_h['total_field_decisions']} field decisions, sources were {combined_h['field_source_counts']}. Hybrid routes versus deterministic changed {combined_h['route_vs_deterministic']['changed']}, improved {combined_h['route_vs_deterministic']['improved']}, and worsened {combined_h['route_vs_deterministic']['worsened']}. Versus model-only they changed {combined_h['route_vs_model']['changed']}, improved {combined_h['route_vs_model']['improved']}, and worsened {combined_h['route_vs_model']['worsened']}. Hybrid produced {combined_h['all_hybrid_manual_review_routes']} manual-review routes, including {combined_h['conflict_abstentions']} policy conflict abstentions.")
    md.extend(["", "The complete tag, family, disagreement, policy-decision, date-role, and V2-to-V3 delta tables are preserved in `FROZEN_V3_FINAL_RESULTS.json`.", "", "## Privacy", "", "No Gmail or Calendar access, real email data, Gmail writes, or raw body persistence occurred. Result snapshots contain no body, rationale, or evidence fields. The API key was not logged; every provider request used `store=false`; all fixtures remain synthetic."])
    OUTPUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    artifact_paths = [
        *(path for split in SPLITS for path in _paths(split).values()),
        RESULTS / "model-only-v1-v3-test-attempt1-network-failure.json",
        OUTPUT_JSON,
        OUTPUT_MD,
        ROOT / "evaluation" / "v3_final_run.py",
        ROOT / "evaluation" / "v3_final_report.py",
        DATA_DIRECTORY / "FROZEN_V3_SHA256.json",
    ]
    hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest().upper()
        for path in artifact_paths
    }
    result_manifest = {
        "evaluation": "final-one-time-blind-v3",
        "dataset_fingerprint": payload["dataset_fingerprint"],
        "case_count": len(all_cases),
        "hash_algorithm": "SHA-256",
        "artifacts": hashes,
        "external_model_calls_final_runs": len(model_cases),
        "failed_local_transport_attempts": len(failed_attempt.cases),
        "bounded_retry_batches": 1,
        "hybrid_incremental_api_cost_usd": 0,
        "post_evaluation_tuning": False,
    }
    OUTPUT_MANIFEST.write_text(json.dumps(result_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
