from __future__ import annotations

import importlib.util
import json
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
    / "apply_semantic_tag_reviews.py"
)


def _load_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "apply_semantic_tag_reviews",
        SCRIPT_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


APPLY_REVIEWS = _load_module()


def _catalogue() -> TagCatalogue:
    return TagCatalogue(
        {
            "schema_version": 1,
            "tags": [
                {
                    "id": "tag_0001",
                    "name": "Social media",
                    "normalized_name": normalize_tag_name("Social media"),
                    "aliases": ["Social networks"],
                    "facets": ["subindustry", "parent:technology"],
                    "merged_into": None,
                },
                {
                    "id": "tag_0002",
                    "name": "Gambling",
                    "normalized_name": normalize_tag_name("Gambling"),
                    "aliases": ["Gaming"],
                    "facets": ["subindustry", "parent:service"],
                    "merged_into": None,
                },
                {
                    "id": "tag_0003",
                    "name": "Casino operations",
                    "normalized_name": normalize_tag_name("Casino operations"),
                    "aliases": [],
                    "facets": ["subindustry", "parent:service"],
                    "merged_into": None,
                },
                {
                    "id": "tag_0004",
                    "name": "Government-owned",
                    "normalized_name": normalize_tag_name("Government-owned"),
                    "aliases": ["State-owned"],
                    "facets": ["status"],
                    "merged_into": None,
                },
            ],
        }
    )


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _dossier(*, record_type: str = "person") -> dict:
    return {
        "schema_version": 8,
        "record_type": record_type,
        "owner": {"person_id": 42, "display_name": "Example Owner"},
        "sources": [{"id": "S1"}],
        "proposed_tags": [],
    }


def _review(dossier_path: Path) -> dict:
    return {
        "schema_version": 1,
        "person_id": 42,
        "display_name": "Example Owner",
        "dossier_sha256": APPLY_REVIEWS._sha256(dossier_path),
        "status": "reviewed",
        "existing_tags_complete": False,
        "canonical_tags": [
            {
                "tag_id": "tag_0001",
                "name": "Social media",
                "summary": "The owner built and controls a social-media company.",
                "confidence": {
                    "score": 95,
                    "band": "very_high",
                    "reason": "The dossier source directly establishes the association.",
                },
                "source_ids": ["S1"],
            }
        ],
        "catalogue_candidates": [],
        "rejected_candidates": [],
        "zero_tag_reason": None,
    }


def test_prepare_reviews_reports_valid_changed_review(tmp_path: Path) -> None:
    dossiers = tmp_path / "dossiers"
    reviews = tmp_path / "reviews"
    dossier_path = dossiers / "42.research.json"
    _write_json(dossier_path, _dossier())
    _write_json(reviews / "42.json", _review(dossier_path))

    prepared = APPLY_REVIEWS.prepare_reviews(dossiers, reviews, _catalogue())

    assert prepared["dossier_count"] == 1
    assert prepared["review_count"] == 1
    assert prepared["rows"][0]["status"] == "reviewed_changed"
    assert prepared["rows"][0]["after"][0]["name"] == "Social media"


def test_reviewed_empty_person_requires_reason(tmp_path: Path) -> None:
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "review.json"
    _write_json(dossier_path, _dossier())
    review = _review(dossier_path)
    review["canonical_tags"] = []
    _write_json(review_path, review)

    with pytest.raises(ValueError, match="zero_tag_reason"):
        APPLY_REVIEWS._validate_review(
            review_path,
            dossier_path,
            _dossier(),
            _catalogue(),
        )


def test_unresolved_placeholder_rejects_tags(tmp_path: Path) -> None:
    dossier = _dossier(record_type="unresolved_placeholder")
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "42.json"
    _write_json(dossier_path, dossier)
    _write_json(review_path, _review(dossier_path))

    with pytest.raises(ValueError, match="unresolved placeholders cannot have tags"):
        APPLY_REVIEWS._validate_review(
            review_path,
            dossier_path,
            dossier,
            _catalogue(),
        )


def test_granular_gambling_requires_umbrella(tmp_path: Path) -> None:
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "42.json"
    dossier = _dossier()
    _write_json(dossier_path, dossier)
    review = _review(dossier_path)
    review["canonical_tags"][0].update(
        {"tag_id": "tag_0003", "name": "Casino operations"}
    )
    _write_json(review_path, review)

    with pytest.raises(ValueError, match="require Gambling"):
        APPLY_REVIEWS._validate_review(
            review_path,
            dossier_path,
            dossier,
            _catalogue(),
        )


def test_government_owned_requires_institution_record(tmp_path: Path) -> None:
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "42.json"
    dossier = _dossier()
    _write_json(dossier_path, dossier)
    review = _review(dossier_path)
    review["canonical_tags"][0].update(
        {"tag_id": "tag_0004", "name": "Government-owned"}
    )
    _write_json(review_path, review)

    with pytest.raises(ValueError, match="requires an institution"):
        APPLY_REVIEWS._validate_review(
            review_path,
            dossier_path,
            dossier,
            _catalogue(),
        )


def test_unresolved_public_entity_can_have_only_evidenced_government_owned(
    tmp_path: Path,
) -> None:
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "42.json"
    dossier = _dossier(record_type="unresolved_placeholder")
    _write_json(dossier_path, dossier)
    review = _review(dossier_path)
    review["canonical_tags"][0].update(
        {"tag_id": "tag_0004", "name": "Government-owned"}
    )
    review["government_owned_basis"] = (
        "Every identity candidate established by the dossier is a public body."
    )
    _write_json(review_path, review)

    normalized, candidates = APPLY_REVIEWS._validate_review(
        review_path,
        dossier_path,
        dossier,
        _catalogue(),
    )

    assert [tag["name"] for tag in normalized] == ["Government-owned"]
    assert candidates == []


def test_unresolved_government_owned_requires_explicit_basis(tmp_path: Path) -> None:
    dossier_path = tmp_path / "42.research.json"
    review_path = tmp_path / "42.json"
    dossier = _dossier(record_type="unresolved_placeholder")
    _write_json(dossier_path, dossier)
    review = _review(dossier_path)
    review["canonical_tags"][0].update(
        {"tag_id": "tag_0004", "name": "Government-owned"}
    )
    _write_json(review_path, review)

    with pytest.raises(ValueError, match="government_owned_basis"):
        APPLY_REVIEWS._validate_review(
            review_path,
            dossier_path,
            dossier,
            _catalogue(),
        )
