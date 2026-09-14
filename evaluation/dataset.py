"""Deterministic loading and fingerprinting of the committed synthetic dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.schemas import DatasetManifest, EvaluationCase


DATA_DIRECTORY = Path(__file__).resolve().parent / "data"
MANIFEST_PATH = DATA_DIRECTORY / "manifest.json"


class DatasetError(ValueError):
    """Raised when committed evaluation data is invalid or inconsistent."""


def load_manifest(path: Path = MANIFEST_PATH) -> DatasetManifest:
    try:
        manifest = DatasetManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DatasetError(f"could not load evaluation manifest: {path.name}") from exc
    if not manifest.split_order or any(not name.strip() for name in manifest.split_order):
        raise DatasetError("evaluation manifest must declare at least one named split")
    if set(manifest.split_order) != set(manifest.split_files):
        raise DatasetError("evaluation manifest split names and files must match")
    return manifest


def _load_jsonl(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DatasetError(f"could not load evaluation split: {path.name}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvaluationCase.model_validate_json(line))
        except ValueError as exc:
            raise DatasetError(
                f"invalid evaluation case in {path.name} line {line_number}"
            ) from exc
    return cases


def load_cases(
    split: str = "all", *, manifest_path: Path = MANIFEST_PATH
) -> tuple[DatasetManifest, list[EvaluationCase], dict[str, int]]:
    manifest = load_manifest(manifest_path)
    if split not in {"all", *manifest.split_order}:
        raise DatasetError(f"unknown evaluation split: {split}")
    selected = manifest.split_order if split == "all" else [split]
    root = manifest_path.parent
    cases: list[EvaluationCase] = []
    split_counts: dict[str, int] = {}
    seen_ids: set[str] = set()
    for split_name in selected:
        relative = manifest.split_files.get(split_name)
        if relative is None:
            raise DatasetError(f"manifest has no file for split: {split_name}")
        split_cases = _load_jsonl(root / relative)
        duplicate_ids = seen_ids.intersection(case.id for case in split_cases)
        if duplicate_ids:
            raise DatasetError(f"duplicate evaluation case id: {min(duplicate_ids)}")
        seen_ids.update(case.id for case in split_cases)
        split_counts[split_name] = len(split_cases)
        cases.extend(split_cases)
    return manifest, cases, split_counts


def dataset_fingerprint(cases: list[EvaluationCase]) -> str:
    digest = hashlib.sha256()
    for case in cases:
        # Excluding fields absent from a historical JSONL record lets the
        # evaluation schema grow without rewriting or re-fingerprinting v1.
        canonical = case.model_dump_json(exclude_none=False, exclude_unset=True)
        digest.update(canonical.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
