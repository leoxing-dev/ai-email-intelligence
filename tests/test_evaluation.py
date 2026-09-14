"""Unit tests for the offline evaluator itself using synthetic records only."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from app.schemas.summary import (
    ActionKind,
    Assessment,
    DateSemanticType,
    EmailType,
    EventStatus,
)
from evaluation import DATASET_VERSION
from evaluation.audit import cross_split_similarities, family_split_violations, structural_statistics
from evaluation.dataset import DATA_DIRECTORY, dataset_fingerprint, load_cases
from evaluation.data.build_v1 import DEV_CASES, TEST_CASES
from evaluation.data.build_v2 import CHALLENGE_CASES, TEST_CASES as V2_TEST_CASES
from evaluation.metrics import (
    binary_metrics,
    compute_date_metrics,
    evaluate,
    route_confusion,
)
from evaluation.schemas import (
    CasePrediction,
    EvaluationCase,
    EvaluationInput,
    EvaluationRoute,
    ExpectedDate,
    GroundTruth,
    EvaluationReport,
    PredictedDate,
)


def _case(
    case_id: str,
    *,
    required: bool = False,
    route: EvaluationRoute = EvaluationRoute.INFORMATIONAL,
    tags: list[str] | None = None,
    dates: list[ExpectedDate] | None = None,
) -> EvaluationCase:
    return EvaluationCase(
        id=case_id,
        input=EvaluationInput(
            subject=f"Synthetic case {case_id}",
            body="Synthetic evaluator content.",
            received_at="2026-09-01T10:00:00-07:00",
        ),
        ground_truth=GroundTruth(
            email_type=EmailType.ADMINISTRATIVE if required else EmailType.AUTOMATED,
            action_kind=ActionKind.REQUIRED if required else ActionKind.NONE,
            needs_reply=Assessment.FALSE,
            contains_event=False,
            event_status=EventStatus.UNCERTAIN,
            registration_available=Assessment.FALSE,
            registration_required=Assessment.FALSE,
            registration_completed=Assessment.UNCERTAIN,
            dates=dates or [],
            expected_route=route,
        ),
        tags=tags or ["synthetic"],
    )


def _prediction(
    case: EvaluationCase,
    *,
    required: bool | None = None,
    route: EvaluationRoute | None = None,
    dates: list[PredictedDate] | None = None,
) -> CasePrediction:
    expected_required = case.ground_truth.action_kind is ActionKind.REQUIRED
    predicted_required = expected_required if required is None else required
    return CasePrediction(
        id=case.id,
        email_type=case.ground_truth.email_type,
        action_kind=ActionKind.REQUIRED if predicted_required else ActionKind.NONE,
        needs_reply=case.ground_truth.needs_reply,
        contains_event=case.ground_truth.contains_event,
        event_status=case.ground_truth.event_status,
        registration_available=case.ground_truth.registration_available,
        registration_required=case.ground_truth.registration_required,
        registration_completed=case.ground_truth.registration_completed,
        dates=dates or [],
        route=route or case.ground_truth.expected_route,
    )


def test_perfect_predictions_produce_perfect_precision_recall_and_f1():
    metric = binary_metrics([True, False, True], [True, False, True])

    assert metric.precision == 1
    assert metric.recall == 1
    assert metric.f1 == 1


def test_false_positive_reduces_precision():
    metric = binary_metrics([True, False], [True, True])

    assert metric.precision == 0.5
    assert metric.recall == 1


def test_false_negative_reduces_recall():
    metric = binary_metrics([True, True], [True, False])

    assert metric.precision == 1
    assert metric.recall == 0.5


def test_all_wrong_positive_predictions_have_zero_f1():
    metric = binary_metrics([True, False], [False, True])

    assert metric.precision == 0
    assert metric.recall == 0
    assert metric.f1 == 0


def test_empty_class_metrics_are_explicitly_undefined():
    metric = binary_metrics([False, False], [False, False])

    assert metric.precision is None
    assert metric.recall is None
    assert metric.f1 is None
    assert metric.tn == 2


def test_route_confusion_counts_expected_and_predicted_routes():
    first = _case("route_case_a", route=EvaluationRoute.NEEDS_ACTION)
    second = _case("route_case_b", route=EvaluationRoute.INFORMATIONAL)
    predictions = [
        _prediction(first, route=EvaluationRoute.NEEDS_ACTION),
        _prediction(second, route=EvaluationRoute.MANUAL_REVIEW),
    ]

    matrix = route_confusion([first, second], predictions)

    assert matrix["needs_action"]["needs_action"] == 1
    assert matrix["informational"]["manual_review"] == 1


def test_date_exact_and_time_tolerance_matching():
    expected_time = datetime.fromisoformat("2026-09-10T13:00:00-07:00")
    case = _case(
        "date_case",
        dates=[
            ExpectedDate(
                value=expected_time,
                semantic_type=DateSemanticType.EVENT_TIME,
            )
        ],
    )

    exact = compute_date_metrics(
        [case],
        [
            _prediction(
                case,
                dates=[
                    PredictedDate(
                        value=expected_time,
                        semantic_type=DateSemanticType.EVENT_TIME,
                    )
                ],
            )
        ],
    )
    tolerant = compute_date_metrics(
        [case],
        [
            _prediction(
                case,
                dates=[
                    PredictedDate(
                        value=expected_time + timedelta(minutes=10),
                        semantic_type=DateSemanticType.EVENT_TIME,
                    )
                ],
            )
        ],
        tolerance_minutes=15,
    )

    assert exact.exact_normalized_match_rate == 1
    assert exact.time_tolerance_accuracy == 1
    assert tolerant.exact_normalized_match_rate == 0
    assert tolerant.time_tolerance_accuracy == 1


def test_per_tag_metrics_use_only_tagged_cases():
    first = _case("tag_case_a", required=True, tags=["promotion"])
    second = _case("tag_case_b", required=False, tags=["security"])
    report = evaluate(
        [first, second],
        [_prediction(first, required=False), _prediction(second)],
        dataset_version=DATASET_VERSION,
        split="dev",
        split_counts={"dev": 2},
    )

    assert report.by_tag["promotion"].cases == 1
    assert report.by_tag["promotion"].binary_metrics["required_action"].fn == 1
    assert report.by_tag["security"].binary_metrics["required_action"].fn == 0


def test_dataset_loading_and_fingerprint_are_reproducible(tmp_path):
    data = tmp_path / "data"
    (data / "dev").mkdir(parents=True)
    (data / "test").mkdir()
    dev_case = _case("load_dev_case")
    test_case = _case("load_test_case")
    (data / "dev" / "cases.jsonl").write_text(
        f"{dev_case.model_dump_json()}\n", encoding="utf-8"
    )
    (data / "test" / "cases.jsonl").write_text(
        f"{test_case.model_dump_json()}\n", encoding="utf-8"
    )
    manifest = {
        "dataset_version": DATASET_VERSION,
        "default_timezone": "America/Los_Angeles",
        "split_order": ["dev", "test"],
        "split_files": {
            "dev": "dev/cases.jsonl",
            "test": "test/cases.jsonl",
        },
        "assignment_policy": "Synthetic deterministic unit-test assignment.",
    }
    manifest_path = data / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    _, first_load, first_counts = load_cases("all", manifest_path=manifest_path)
    _, second_load, second_counts = load_cases("all", manifest_path=manifest_path)

    assert [case.id for case in first_load] == ["load_dev_case", "load_test_case"]
    assert first_load == second_load
    assert first_counts == second_counts == {"dev": 1, "test": 1}
    assert dataset_fingerprint(first_load) == dataset_fingerprint(second_load)


def test_committed_v1_dataset_has_fixed_splits_and_required_coverage():
    manifest, cases, counts = load_cases("all")

    assert manifest.dataset_version == DATASET_VERSION
    assert counts == {"dev": 65, "test": 35}
    assert len(cases) == 100
    assert len({case.id for case in cases}) == 100
    assert {"dev", "test"} == set(manifest.split_order)
    tags = {tag for case in cases for tag in case.tags}
    assert {
        "required_action",
        "conditional",
        "event",
        "registration",
        "relative_date",
        "timezone",
        "newsletter",
        "digest",
        "html_noise",
        "security",
        "reply",
    } <= tags


def test_committed_jsonl_matches_deterministic_v1_builder():
    _, dev_cases, _ = load_cases("dev")
    _, test_cases, _ = load_cases("test")

    assert [case.model_dump(mode="json") for case in dev_cases] == DEV_CASES
    assert [case.model_dump(mode="json") for case in test_cases] == TEST_CASES


def test_committed_benchmark_contains_no_live_account_domain_or_credentials():
    _, cases, _ = load_cases("all")
    serialized = "\n".join(case.model_dump_json() for case in cases).casefold()

    assert "@usc.edu" not in serialized
    assert "credentials.json" not in serialized
    assert "token.json" not in serialized
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert all(".example" in case.input.sender for case in cases)


def test_stored_baseline_matches_held_out_dataset_fingerprint():
    baseline_path = (
        Path(__file__).parents[1]
        / "evaluation"
        / "baselines"
        / "deterministic-baseline-v1.json"
    )
    baseline = EvaluationReport.model_validate_json(
        baseline_path.read_text(encoding="utf-8")
    )
    _, cases, counts = load_cases("test")

    assert baseline.baseline_id == "deterministic-baseline-v1"
    assert baseline.split == "test"
    assert baseline.case_count == 35
    assert baseline.split_counts == counts
    assert baseline.dataset_fingerprint == dataset_fingerprint(cases)
    serialized = baseline.model_dump_json().casefold()
    assert '"subject"' not in serialized
    assert '"body"' not in serialized
    assert '"sender"' not in serialized


def test_v2_has_fixed_family_level_splits_and_challenge_coverage():
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    manifest, cases, counts = load_cases("all", manifest_path=manifest_path)

    assert manifest.dataset_version == "synthetic-email-benchmark-v2"
    assert counts == {"v2_dev": 100, "v2_test": 52, "challenge": 66}
    assert len(cases) == 218
    assert len({case.id for case in cases}) == 218
    by_split = {
        name: load_cases(name, manifest_path=manifest_path)[1]
        for name in manifest.split_order
    }
    assert family_split_violations(by_split) == {}
    assert all(case.family_id for case in cases)
    challenge_tags = {tag for case in by_split["challenge"] for tag in case.tags}
    assert {
        "adversarial", "ambiguous", "container", "dst_boundary",
        "forwarded", "html_noise", "implicit_obligation", "long_body",
        "malformed_encoding", "minimal_pair", "obsolete_deadline",
        "preheader", "quoted_reply", "registration_completed",
        "trigger_negative", "utc_boundary",
    } <= challenge_tags


def test_committed_v2_new_splits_match_deterministic_builder():
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    _, test_cases, _ = load_cases("v2_test", manifest_path=manifest_path)
    _, challenge_cases, _ = load_cases("challenge", manifest_path=manifest_path)

    assert [case.model_dump(mode="json") for case in test_cases] == V2_TEST_CASES
    assert [case.model_dump(mode="json") for case in challenge_cases] == CHALLENGE_CASES


def test_v2_held_out_samples_and_structure_are_materially_stronger_than_v1():
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    _, v2_test, _ = load_cases("v2_test", manifest_path=manifest_path)
    _, challenge, _ = load_cases("challenge", manifest_path=manifest_path)
    test_stats = structural_statistics(v2_test)
    challenge_stats = structural_statistics(challenge)

    assert test_stats["task_balance"]["registration_required"]["positive"] >= 5
    assert test_stats["task_balance"]["registration_completed"]["positive"] >= 5
    assert test_stats["task_balance"]["needs_reply"]["positive"] >= 5
    assert challenge_stats["manual_review_cases"] >= 5
    assert challenge_stats["multi_date_cases"] >= 10
    assert challenge_stats["average_body_characters"] > 100


def test_v1_similarity_audit_detects_cross_split_template_candidates():
    _, dev, _ = load_cases("dev")
    _, test, _ = load_cases("test")

    matches = cross_split_similarities(dev, test, threshold=0.35)

    assert len(matches) >= 10


def test_malformed_challenge_payload_abstains_without_crashing():
    from evaluation.pipeline import predict_cases

    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    manifest, challenge, _ = load_cases("challenge", manifest_path=manifest_path)
    malformed = [case for case in challenge if "malformed_encoding" in case.tags]
    predictions = predict_cases(malformed, timezone_name=manifest.default_timezone)

    assert len(predictions) == 2
    assert any(item.route is EvaluationRoute.MANUAL_REVIEW for item in predictions)


def test_stored_v2_reports_match_current_dataset_without_fixture_text():
    root = Path(__file__).parents[1]
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    for split, filename in (
        ("all", "unchanged-deterministic-v2.json"),
        ("challenge", "unchanged-deterministic-v2-challenge.json"),
    ):
        report = EvaluationReport.model_validate_json(
            (root / "evaluation" / "baselines" / filename).read_text(encoding="utf-8")
        )
        _, cases, counts = load_cases(split, manifest_path=manifest_path)
        assert report.dataset_version == "synthetic-email-benchmark-v2"
        assert report.split == split
        assert report.split_counts == counts
        assert report.dataset_fingerprint == dataset_fingerprint(cases)
        serialized = report.model_dump_json().casefold()
        assert '"subject"' not in serialized
        assert '"body"' not in serialized
        assert '"sender"' not in serialized


def test_deterministic_rules_v2_snapshots_match_frozen_splits():
    root = Path(__file__).parents[1]
    manifest_path = DATA_DIRECTORY / "manifest_v2.json"
    for split in ("v2_dev", "v2_test", "challenge"):
        report = EvaluationReport.model_validate_json(
            (
                root
                / "evaluation"
                / "baselines"
                / f"deterministic-rules-v2-{split.removeprefix('v2_')}.json"
            ).read_text(encoding="utf-8")
        )
        _, cases, counts = load_cases(split, manifest_path=manifest_path)
        assert report.baseline_id == "deterministic-rules-v2"
        assert report.split == split
        assert report.split_counts == counts
        assert report.dataset_fingerprint == dataset_fingerprint(cases)
        serialized = report.model_dump_json().casefold()
        assert '"subject"' not in serialized
        assert '"body"' not in serialized
        assert '"sender"' not in serialized


def test_historical_data_and_baseline_hashes_are_frozen():
    root = Path(__file__).parents[1]
    expected = json.loads(
        (root / "evaluation" / "data" / "FROZEN_SHA256.json").read_text(
            encoding="utf-8"
        )
    )

    observed = {
        relative: hashlib.sha256((root / relative).read_bytes()).hexdigest().upper()
        for relative in expected
    }

    assert observed == expected
