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
    / "activate_corpus_tag_manifest.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent


def _load_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        specification = importlib.util.spec_from_file_location(
            "activate_corpus_tag_manifest",
            SCRIPT_PATH,
        )
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_DIR))


ACTIVATE = _load_module()


def _contract() -> dict[str, str]:
    return {
        "dimension": "industry_or_investment_specialism",
        "membership": "The owner built or controlled the operating business.",
        "exclusions": "Exclude passive investors and incidental exposure.",
        "temporal_scope": "current_or_historically_defining",
        "click_through_expectation": "Users see comparable defining operators.",
    }


def _concept(name: str) -> dict:
    return {
        "name": name,
        "aliases": [],
        "facets": ["occupation"],
        "relationship_contract": "Include defining long-term operators.",
        "semantic_contract": _contract(),
        "click_through_expectation": "Users see comparable defining operators.",
        "known_for_basis": "Each owner is publicly known for the role.",
        "existing_active_review": "No active tag captures the relationship.",
        "broader_tag_review": "The broader option loses useful distinction.",
        "facet_review": "The precision is useful as a literal cohort.",
        "dossier_metadata_review": "This is not owner-specific detail.",
        "information_value": "The cohort supports a meaningful comparison.",
        "dossier_records": [
            {
                "person_id": 1,
                "dossier": "output/owner-research/1.research.json",
                "membership_basis": "The dossier establishes the role.",
            },
            {
                "person_id": 2,
                "dossier": "output/owner-research/2.research.json",
                "membership_basis": "The dossier establishes the role.",
            },
        ],
    }


def _manifest(*concepts: dict) -> dict:
    return {
        "schema_version": 1,
        "scope": "corpus_owner_tag_discovery",
        "review_status": "approved_for_candidate_queue",
        "review_reference": "corpus review 2026-09-18",
        "concepts": list(concepts),
    }


def _tag(tag_id: str, name: str, status: str) -> dict:
    lifecycle = {"reason": "corpus_level_taxonomy_discovery"}
    if status == "inactive":
        lifecycle.update(
            {
                "reason": "previously_too_small",
                "consolidation_decision": "retained_inactive",
            }
        )
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": [],
        "facets": ["occupation"],
        "status": status,
        "merged_into": None,
        "lifecycle": lifecycle,
    }


def test_candidate_and_inactive_concepts_activate_with_contracts() -> None:
    document = {
        "schema_version": 2,
        "tags": [
            _tag("tag_0001", "Candidate concept", "candidate"),
            _tag("tag_0002", "Inactive concept", "inactive"),
        ],
    }
    updated, report = ACTIVATE.prepare_activation(
        document,
        _manifest(_concept("Candidate concept"), _concept("Inactive concept")),
        approval_reference="user-approved backfill 2026-09-18",
    )

    catalogue = TagCatalogue(updated)
    assert catalogue.all_tags_by_id["tag_0001"].status == "active"
    assert catalogue.all_tags_by_id["tag_0002"].status == "active"
    assert updated["tags"][0]["semantic_contract"] == _contract()
    assert updated["tags"][1]["semantic_contract"] == _contract()
    assert updated["tags"][0]["lifecycle"]["promoted_from"] == "candidate"
    assert updated["tags"][1]["lifecycle"]["reactivated_from"] == "inactive"
    assert "reason" not in updated["tags"][1]["lifecycle"]
    assert [result["status"] for result in report["results"]] == [
        "promoted",
        "reactivated",
    ]


def test_activation_requires_registered_concepts() -> None:
    unrelated = _tag("tag_0001", "Unrelated concept", "active")
    unrelated["semantic_contract"] = _contract()
    with pytest.raises(ValueError, match="registered before activation"):
        ACTIVATE.prepare_activation(
            {"schema_version": 2, "tags": [unrelated]},
            _manifest(_concept("Missing concept")),
            approval_reference="user-approved backfill 2026-09-18",
        )


def test_active_concept_with_different_contract_is_not_rewritten() -> None:
    active = _tag("tag_0001", "Active concept", "active")
    active["semantic_contract"] = {
        **_contract(),
        "membership": "A different reviewed membership rule.",
    }
    with pytest.raises(ValueError, match="different semantic contract"):
        ACTIVATE.prepare_activation(
            {"schema_version": 2, "tags": [active]},
            _manifest(_concept("Active concept")),
            approval_reference="user-approved backfill 2026-09-18",
        )
