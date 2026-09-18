from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from src.tags import normalize_tag_name


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "backfill_corpus_tag_manifest.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent


def _load_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        specification = importlib.util.spec_from_file_location(
            "backfill_corpus_tag_manifest",
            SCRIPT_PATH,
        )
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_DIR))


BACKFILL = _load_module()


def _contract() -> dict[str, str]:
    return {
        "dimension": "industry_or_investment_specialism",
        "membership": "The owner built or controlled a commercial marina.",
        "exclusions": "Exclude berth users and passive investors.",
        "temporal_scope": "current_or_historically_defining",
        "click_through_expectation": "Users see defining marina operators.",
    }


def _concept() -> dict:
    return {
        "name": "Marina operations",
        "aliases": [],
        "facets": ["occupation"],
        "relationship_contract": "Include defining long-term operators.",
        "semantic_contract": _contract(),
        "click_through_expectation": "Users see defining marina operators.",
        "known_for_basis": "Each owner is publicly known for the role.",
        "existing_active_review": "The active tag has now been approved.",
        "broader_tag_review": "The broader option loses useful distinction.",
        "facet_review": "The precision is useful as a literal cohort.",
        "dossier_metadata_review": "This is not owner-specific detail.",
        "information_value": "The cohort supports a meaningful comparison.",
        "dossier_records": [
            {
                "person_id": 1,
                "dossier": "dossiers/1.research.json",
                "membership_basis": "First Owner founded Alpha Marina.",
            },
            {
                "person_id": 2,
                "dossier": "dossiers/2.research.json",
                "membership_basis": "Second Owner controls Beta Marina.",
            },
        ],
    }


def _manifest() -> dict:
    return {
        "schema_version": 1,
        "scope": "corpus_owner_tag_discovery",
        "review_status": "approved_for_candidate_queue",
        "review_reference": "corpus review 2026-09-18",
        "concepts": [_concept()],
    }


def _catalogue() -> dict:
    return {
        "schema_version": 2,
        "tags": [
            {
                "id": "tag_0001",
                "name": "Marina operations",
                "normalized_name": normalize_tag_name("Marina operations"),
                "aliases": [],
                "facets": ["occupation"],
                "status": "active",
                "merged_into": None,
                "lifecycle": {},
                "semantic_contract": _contract(),
            },
            {
                "id": "tag_0002",
                "name": "Existing tag",
                "normalized_name": normalize_tag_name("Existing tag"),
                "aliases": [],
                "facets": ["occupation"],
                "status": "active",
                "merged_into": None,
                "lifecycle": {},
                "semantic_contract": _contract(),
            },
        ],
    }


def _dossier(person_id: int, name: str, marina: str) -> dict:
    return {
        "schema_version": 8,
        "record_type": "person",
        "research_status": "complete",
        "owner": {"person_id": person_id, "display_name": name},
        "review": {"status": "complete"},
        "biography": {
            "plain_text": f"{name} founded and operates {marina}.",
            "source_ids": ["S1"],
        },
        "long_biography": {
            "plain_text": f"The commercial marina is a defining business.",
            "source_ids": ["S1"],
        },
        "biography_brief": {
            "durable_identity": f"Founder of {marina}.",
            "source_ids": ["S1"],
        },
        "wealth_creation_industry": {
            "summary": "Wealth came from marina operations.",
            "source_ids": ["S1"],
        },
        "primary_industry": {
            "summary": "Current marina operator.",
            "source_ids": ["S1"],
        },
        "wealth_origin": {"summary": "Self-made.", "source_ids": ["S1"]},
        "wealth_relationship": {
            "summary": "Founder and operator.",
            "source_ids": ["S1"],
        },
        "sources": [
            {
                "id": "S1",
                "title": f"{marina} company profile",
                "publisher": marina,
                "tier": 1,
                "supports": [f"{name} founded and operates the marina."],
            }
        ],
        "proposed_tags": [
            {
                "tag_id": "tag_0002",
                "name": "Existing tag",
                "summary": "Existing reviewed assignment.",
                "confidence": {
                    "score": 90,
                    "band": "high",
                    "reason": "Existing evidence.",
                },
                "source_ids": ["S1"],
            }
        ],
    }


def _write_dossiers(tmp_path: Path) -> Path:
    root = tmp_path / "dossiers"
    root.mkdir()
    for person_id, name, marina in (
        (1, "First Owner", "Alpha Marina"),
        (2, "Second Owner", "Beta Marina"),
    ):
        (root / f"{person_id}.research.json").write_text(
            json.dumps(_dossier(person_id, name, marina)),
            encoding="utf-8",
        )
    return root


def test_manifest_backfill_is_exact_and_additive(tmp_path: Path) -> None:
    dossier_root = _write_dossiers(tmp_path)

    prepared = BACKFILL.prepare_backfill(
        _manifest(),
        _catalogue(),
        repo_root=tmp_path,
        dossier_root=dossier_root,
    )

    assert prepared["manifest_record_count"] == 2
    assert prepared["distinct_owner_count"] == 2
    assert prepared["status_counts"] == {"add": 2}
    for row in prepared["rows"]:
        assert row["before"][0]["name"] == "Existing tag"
        assert {item["name"] for item in row["after"]} == {
            "Existing tag",
            "Marina operations",
        }
        assert row["proposal"]["source_ids"] == ["S1"]
        assert row["proposal"]["confidence"]["score"] == 95


def test_non_manifest_assignment_is_rejected(tmp_path: Path) -> None:
    dossier_root = _write_dossiers(tmp_path)
    extra = _dossier(3, "Unexpected Owner", "Gamma Marina")
    extra["proposed_tags"].append(
        {
            "tag_id": "tag_0001",
            "name": "Marina operations",
            "summary": "Unexpected assignment.",
            "confidence": {
                "score": 90,
                "band": "high",
                "reason": "Unexpected evidence.",
            },
            "source_ids": ["S1"],
        }
    )
    (dossier_root / "3.research.json").write_text(
        json.dumps(extra), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="non-manifest dossiers"):
        BACKFILL.prepare_backfill(
            _manifest(),
            _catalogue(),
            repo_root=tmp_path,
            dossier_root=dossier_root,
        )
