"""Audit V3 construction without importing or executing any classifier."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from app.schemas.summary import ActionKind, Assessment, DateSemanticType, EventStatus
from evaluation.dataset import DATA_DIRECTORY, dataset_fingerprint, load_cases
from evaluation.schemas import EvaluationRoute


OUTPUT = DATA_DIRECTORY / "v3_audit.json"
TOKEN = re.compile(r"[a-z0-9\u4e00-\u9fff]+")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tokens(subject: str, body: str) -> set[str]:
    return set(TOKEN.findall(f"{subject} {body}".casefold()))


def _similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def main() -> None:
    manifest_path = DATA_DIRECTORY / "manifest_v3.json"
    manifest, all_cases, split_counts = load_cases("all", manifest_path=manifest_path)
    by_split = {}
    for split in manifest.split_order:
        _, cases, _ = load_cases(split, manifest_path=manifest_path)
        by_split[split] = cases
    metadata = _read_jsonl(DATA_DIRECTORY / "v3_case_metadata.jsonl")
    metadata_by_id = {item["id"]: item for item in metadata}
    family_map = json.loads((DATA_DIRECTORY / "v3_family_mapping.json").read_text(encoding="utf-8"))
    if set(metadata_by_id) != {case.id for case in all_cases}:
        raise RuntimeError("V3 metadata IDs do not match case IDs")

    def positive_counts(cases):
        return {
            "required_action": sum(c.ground_truth.action_kind is ActionKind.REQUIRED for c in cases),
            "event": sum(c.ground_truth.contains_event for c in cases),
            "upcoming_event": sum(c.ground_truth.event_status is EventStatus.UPCOMING for c in cases),
            "registration_required": sum(c.ground_truth.registration_required is Assessment.TRUE for c in cases),
            "registration_completed": sum(c.ground_truth.registration_completed is Assessment.TRUE for c in cases),
            "deadline": sum(any(d.semantic_type in {DateSemanticType.DEADLINE, DateSemanticType.REGISTRATION_DEADLINE} for d in c.ground_truth.dates) for c in cases),
            "needs_reply": sum(c.ground_truth.needs_reply is Assessment.TRUE for c in cases),
        }

    class_balance = {}
    for split, cases in {**by_split, "total": all_cases}.items():
        positives = positive_counts(cases)
        class_balance[split] = {
            name: {"positive": count, "non_positive": len(cases) - count}
            for name, count in positives.items()
        }

    difficulty = Counter(item["difficulty"] for item in metadata)
    difficulty_by_split = {
        split: dict(Counter(metadata_by_id[c.id]["difficulty"] for c in cases))
        for split, cases in by_split.items()
    }
    tags = Counter(tag for case in all_cases for tag in case.tags)
    families_by_split = {
        split: len({case.family_id for case in cases}) for split, cases in by_split.items()
    }
    family_splits = defaultdict(set)
    for split, cases in by_split.items():
        for case in cases:
            family_splits[case.family_id].add(split)
    shared_families = sorted(name for name, splits in family_splits.items() if len(splits) > 1)

    subject_lengths = [len(c.input.subject) for c in all_cases]
    body_lengths = [len(c.input.body) for c in all_cases]
    body_words = [len(TOKEN.findall(c.input.body.casefold())) for c in all_cases]
    structural = {
        "average_subject_characters": sum(subject_lengths) / len(subject_lengths),
        "average_body_characters": sum(body_lengths) / len(body_lengths),
        "average_body_words": sum(body_words) / len(body_words),
        "long_form_cases": sum("long_form" in c.tags or len(c.input.body) >= 1200 for c in all_cases),
        "multi_date_cases": sum(len(c.ground_truth.dates) >= 2 for c in all_cases),
        "multi_event_cases": sum(sum(d.semantic_type is DateSemanticType.EVENT_TIME for d in c.ground_truth.dates) >= 2 for c in all_cases),
        "digest_or_container_cases": sum("digest" in c.tags or "container" in c.tags for c in all_cases),
        "html_or_noise_cases": sum(c.input.body_format == "html" or "html_noise" in c.tags for c in all_cases),
        "ambiguous_or_manual_review_cases": sum(c.ground_truth.expected_route is EvaluationRoute.MANUAL_REVIEW or "ambiguous" in c.tags for c in all_cases),
        "timezone_or_dst_cases": sum("timezone" in c.tags or "dst_boundary" in c.tags for c in all_cases),
        "multilingual_or_encoding_cases": sum("multilingual" in c.tags or "encoding" in c.tags or c.input.encoding_mode != "valid" for c in all_cases),
    }

    normalized = [
        " ".join(TOKEN.findall(f"{c.input.subject} {c.input.body}".casefold()))
        for c in all_cases
    ]
    exact_duplicates = len(normalized) - len(set(normalized))
    token_sets = {c.id: _tokens(c.input.subject, c.input.body) for c in all_cases}
    cross_split_matches = []
    for left in by_split["v3_test"]:
        for right in by_split["v3_challenge"]:
            score = _similarity(token_sets[left.id], token_sets[right.id])
            if score >= 0.55:
                cross_split_matches.append((score, left.id, right.id))
    cross_family_matches = []
    for split, cases in by_split.items():
        for index, left in enumerate(cases):
            for right in cases[index + 1 :]:
                if left.family_id == right.family_id:
                    continue
                score = _similarity(token_sets[left.id], token_sets[right.id])
                if score >= 0.75:
                    cross_family_matches.append((score, left.id, right.id, split))

    prior_cases = []
    for relative in (
        "dev/cases.jsonl",
        "test/cases.jsonl",
        "v2_dev/cases.jsonl",
        "v2_test/cases.jsonl",
        "challenge/cases.jsonl",
    ):
        prior_cases.extend(_read_jsonl(DATA_DIRECTORY / relative))
    prior_tokens = {
        item["id"]: _tokens(item["input"]["subject"], item["input"]["body"])
        for item in prior_cases
    }
    prior_matches = []
    for case in all_cases:
        for prior_id, tokens in prior_tokens.items():
            score = _similarity(token_sets[case.id], tokens)
            if score >= 0.45:
                prior_matches.append((score, case.id, prior_id))

    sender_domains = {
        match.group(1).casefold()
        for case in all_cases
        for match in [re.search(r"@([^>\s]+)", case.input.sender)]
        if match
    }
    audit = {
        "dataset_version": manifest.dataset_version,
        "dataset_fingerprint": dataset_fingerprint(all_cases),
        "split_counts": split_counts,
        "split_fingerprints": {
            split: dataset_fingerprint(cases) for split, cases in by_split.items()
        },
        "family_count": len(family_map),
        "families_by_split": families_by_split,
        "shared_scenario_families": shared_families,
        "cases_per_family": dict(sorted(Counter(c.family_id for c in all_cases).items())),
        "difficulty_distribution": dict(difficulty),
        "difficulty_by_split": difficulty_by_split,
        "class_balance": class_balance,
        "tag_counts": dict(sorted(tags.items())),
        "route_counts": dict(Counter(c.ground_truth.expected_route.value for c in all_cases)),
        "structural_counts": structural,
        "duplicate_audit": {
            "exact_duplicate_count": exact_duplicates,
            "cross_split_jaccard_threshold": 0.55,
            "cross_split_near_duplicate_count": len(cross_split_matches),
            "cross_split_top_matches": sorted(cross_split_matches, reverse=True)[:20],
            "cross_family_jaccard_threshold": 0.75,
            "cross_family_near_duplicate_count": len(cross_family_matches),
            "cross_family_top_matches": sorted(cross_family_matches, reverse=True)[:20],
            "same_template_variant_families": len(family_map),
            "variants_per_family": 6,
            "prior_version_jaccard_threshold": 0.45,
            "prior_version_near_duplicate_count": len(prior_matches),
            "prior_version_top_matches": sorted(prior_matches, reverse=True)[:20],
        },
        "privacy": {
            "all_synthetic_marker_present": all(c.input.headers.get("X-Synthetic-Benchmark") == manifest.dataset_version for c in all_cases),
            "sender_domains": sorted(sender_domains),
            "all_sender_domains_reserved_example": all(domain.endswith(".example") for domain in sender_domains),
            "metadata_rationale_count": len(metadata),
        },
    }
    OUTPUT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
