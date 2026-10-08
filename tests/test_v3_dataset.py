from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from evaluation.dataset import DATA_DIRECTORY, dataset_fingerprint, load_cases


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = DATA_DIRECTORY / "manifest_v3.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_v3_manifest_counts_fingerprints_and_family_isolation() -> None:
    manifest, cases, counts = load_cases("all", manifest_path=MANIFEST)
    _, test_cases, _ = load_cases("v3_test", manifest_path=MANIFEST)
    _, challenge_cases, _ = load_cases("v3_challenge", manifest_path=MANIFEST)
    audit = _json(DATA_DIRECTORY / "v3_audit.json")

    assert manifest.dataset_version == "synthetic-email-benchmark-v3-blind"
    assert counts == {"v3_test": 186, "v3_challenge": 126}
    assert len(cases) == 312
    assert len({case.id for case in cases}) == 312
    assert {case.family_id for case in test_cases}.isdisjoint(
        {case.family_id for case in challenge_cases}
    )
    assert dataset_fingerprint(cases) == audit["dataset_fingerprint"]
    assert dataset_fingerprint(test_cases) == audit["split_fingerprints"]["v3_test"]
    assert dataset_fingerprint(challenge_cases) == audit["split_fingerprints"]["v3_challenge"]


def test_v3_metadata_balance_and_privacy_invariants() -> None:
    _, cases, _ = load_cases("all", manifest_path=MANIFEST)
    metadata = [
        json.loads(line)
        for line in (DATA_DIRECTORY / "v3_case_metadata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    audit = _json(DATA_DIRECTORY / "v3_audit.json")

    assert len(metadata) == len(cases)
    assert {item["id"] for item in metadata} == {case.id for case in cases}
    assert all(item["ground_truth_rationale"].strip() for item in metadata)
    assert all(item["difficulty"] in {"easy", "medium", "hard", "adversarial"} for item in metadata)
    assert sum(audit["difficulty_distribution"].get(level, 0) for level in ("hard", "adversarial")) >= 208
    assert all(
        audit["class_balance"]["total"][target]["positive"] >= 24
        for target in (
            "required_action",
            "event",
            "upcoming_event",
            "registration_required",
            "registration_completed",
            "deadline",
            "needs_reply",
        )
    )
    assert all(case.input.headers["X-Synthetic-Benchmark"] == "synthetic-email-benchmark-v3-blind" for case in cases)
    assert all(re.search(r"@[^>\s]+\.example>", case.input.sender) for case in cases)


def test_v3_duplicate_audit_is_clean() -> None:
    duplicate = _json(DATA_DIRECTORY / "v3_audit.json")["duplicate_audit"]
    assert duplicate["exact_duplicate_count"] == 0
    assert duplicate["cross_split_near_duplicate_count"] == 0
    assert duplicate["cross_family_near_duplicate_count"] == 0
    assert duplicate["prior_version_near_duplicate_count"] == 0


def test_v3_freeze_hashes() -> None:
    freeze = _json(DATA_DIRECTORY / "FROZEN_V3_SHA256.json")
    for relative, expected in freeze["sha256"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper()
        assert actual == expected, relative
