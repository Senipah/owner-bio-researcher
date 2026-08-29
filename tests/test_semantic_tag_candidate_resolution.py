from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from src.tags import TagCatalogue, normalize_tag_name


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "resolve_semantic_tag_candidates.py"
)


def _load_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "resolve_semantic_tag_candidates",
        SCRIPT_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


RESOLVE = _load_module()


def _tag(tag_id: str, name: str, *, aliases: list[str] | None = None) -> dict:
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": aliases or [],
        "facets": ["occupation"],
        "merged_into": None,
    }


def _catalogue() -> dict:
    return {"schema_version": 1, "tags": [_tag("tag_0001", "Film director")]}


def _candidate(name: str, *, aliases: list[str] | None = None) -> dict:
    return {
        "name": name,
        "aliases": aliases or [],
        "facets": ["occupation"],
        "summary": f"The owner is materially associated with {name}.",
        "confidence": 96,
        "source_ids": ["S1"],
    }


def _review(*candidates: dict) -> dict:
    return {
        "person_id": 42,
        "canonical_tags": [],
        "catalogue_candidates": list(candidates),
        "rejected_candidates": [],
    }


def test_add_creates_tag_and_updates_review(tmp_path: Path) -> None:
    review_path = tmp_path / "42.json"
    reviews = [(review_path, _review(_candidate("Film producer")))]
    decisions = {
        "schema_version": 1,
        "approval_status": "approved",
        "decisions": [
            {
                "candidate": "Film producer",
                "action": "add",
                "aliases": ["Movie producer"],
                "facets": ["occupation"],
            }
        ],
    }

    catalogue, updated_reviews, report = RESOLVE.prepare_resolution(
        _catalogue(), reviews, decisions
    )

    created = TagCatalogue(catalogue).resolve(tag_id=None, name="Movie producer")
    assert created.name == "Film producer"
    assert report["candidate_group_count"] == 1
    assert updated_reviews[0][1]["catalogue_candidates"] == []
    assert updated_reviews[0][1]["canonical_tags"][0]["tag_id"] == created.id


def test_add_accepts_structured_candidate_confidence(tmp_path: Path) -> None:
    candidate = _candidate("Film producer")
    candidate["confidence"] = {
        "score": 97,
        "band": "very_high",
        "reason": "The reviewed sources directly establish the occupation.",
    }
    reviews = [(tmp_path / "42.json", _review(candidate))]
    decisions = {
        "schema_version": 1,
        "approval_status": "approved",
        "decisions": [
            {
                "candidate": "Film producer",
                "action": "add",
                "facets": ["occupation"],
            }
        ],
    }

    _, updated_reviews, _ = RESOLVE.prepare_resolution(
        _catalogue(), reviews, decisions
    )

    confidence = updated_reviews[0][1]["canonical_tags"][0]["confidence"]
    assert confidence == candidate["confidence"]


def test_merge_records_alias_and_reject_documents_reason(tmp_path: Path) -> None:
    review_path = tmp_path / "42.json"
    reviews = [
        (
            review_path,
            _review(
                _candidate("Movie director"),
                _candidate("Incidental pastime"),
            ),
        )
    ]
    decisions = {
        "schema_version": 1,
        "approval_status": "approved",
        "decisions": [
            {
                "candidate": "Movie director",
                "action": "merge",
                "canonical": "Film director",
            },
            {
                "candidate": "Incidental pastime",
                "action": "reject",
                "reason": "Not a durable or material association.",
            },
        ],
    }

    catalogue, updated_reviews, _ = RESOLVE.prepare_resolution(
        _catalogue(), reviews, decisions
    )

    merged = TagCatalogue(catalogue).resolve(tag_id=None, name="Movie director")
    assert merged.id == "tag_0001"
    review = updated_reviews[0][1]
    assert review["catalogue_candidates"] == []
    assert review["canonical_tags"][0]["tag_id"] == "tag_0001"
    assert review["rejected_candidates"] == [
        {
            "name": "Incidental pastime",
            "reason": "Not a durable or material association.",
        }
    ]


def test_decisions_must_exactly_cover_candidates(tmp_path: Path) -> None:
    reviews = [(tmp_path / "42.json", _review(_candidate("Film producer")))]

    with pytest.raises(ValueError, match="candidate decisions do not match"):
        RESOLVE.prepare_resolution(
            _catalogue(),
            reviews,
            {
                "schema_version": 1,
                "approval_status": "approved",
                "decisions": [],
            },
        )


def test_rejection_reason_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="reason is required"):
        RESOLVE._decision_map(
            {
                "schema_version": 1,
                "approval_status": "approved",
                "decisions": [
                    {
                        "candidate": "Incidental pastime",
                        "action": "reject",
                        "reason": "   ",
                    }
                ],
            }
        )


def test_draft_decisions_cannot_be_applied() -> None:
    with pytest.raises(ValueError, match="approval_status must be approved"):
        RESOLVE._decision_map(
            {
                "schema_version": 1,
                "approval_status": "draft",
                "decisions": [],
            }
        )
