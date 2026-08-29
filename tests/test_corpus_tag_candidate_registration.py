from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
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
    / "register_corpus_tag_candidates.py"
)


def _load_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "register_corpus_tag_candidates",
        SCRIPT_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


REGISTER = _load_module()


def _tag(
    tag_id: str,
    name: str,
    status: str,
    *,
    aliases: list[str] | None = None,
    merged_into: str | None = None,
) -> dict:
    lifecycle = {}
    if status == "inactive":
        lifecycle["reason"] = "globally_rejected"
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": aliases or [],
        "facets": ["occupation"],
        "status": status,
        "merged_into": merged_into,
        "lifecycle": lifecycle,
    }


def _catalogue() -> dict:
    return {
        "schema_version": 2,
        "tags": [
            _tag("tag_0001", "Active concept", "active", aliases=["Active alias"]),
            _tag("tag_0002", "Candidate concept", "candidate"),
            _tag("tag_0003", "Inactive concept", "inactive"),
            _tag(
                "tag_0004",
                "Merged concept",
                "merged",
                merged_into="tag_0001",
            ),
        ],
    }


def _concept(name: str, record_count: int = 2) -> dict:
    return {
        "name": name,
        "aliases": [],
        "facets": ["occupation", "specialist"],
        "relationship_contract": "Members are defining long-term operators.",
        "click_through_expectation": "Users see owners known for the same role.",
        "known_for_basis": "Each owner is publicly known for the role.",
        "existing_active_review": "No active tag captures the relationship.",
        "broader_tag_review": "The broader option loses useful distinction.",
        "facet_review": "The precision is useful as a literal cohort.",
        "dossier_metadata_review": "This is not merely owner-specific detail.",
        "information_value": "The cohort supports a meaningful owner comparison.",
        "dossier_records": [
            {
                "person_id": index + 1,
                "dossier": f"output/owner-research/{index + 1}.research.json",
                "membership_basis": "The dossier establishes the defining role.",
            }
            for index in range(record_count)
        ],
    }


def _manifest(*concepts: dict) -> dict:
    return {
        "schema_version": 1,
        "scope": "corpus_owner_tag_discovery",
        "review_status": "approved_for_candidate_queue",
        "review_reference": "corpus review 2026-08-29",
        "concepts": list(concepts),
    }


def test_corpus_review_can_create_candidate_but_not_activate_it() -> None:
    original = _catalogue()
    before = deepcopy(original)

    updated, report = REGISTER.prepare_registration(
        original,
        _manifest(_concept("Cross-owner specialist role", record_count=6)),
    )

    created = report["results"][0]
    assert created["outcome"] == "candidate_created"
    assert created["soft_frequency_signal"] == "within_soft_range"
    assert created["candidate"]["status"] == "candidate"
    assert created["candidate"]["id"] == "tag_0005"
    assert updated["tags"] != original["tags"]
    assert original == before
    assert all(
        tag["status"] != "active"
        for tag in updated["tags"]
        if tag["id"] == "tag_0005"
    )
    assert report["automatic_activation"] is False


def test_single_owner_cannot_enter_formal_candidate_queue() -> None:
    with pytest.raises(ValueError, match="at least two dossier records"):
        REGISTER.prepare_registration(
            _catalogue(),
            _manifest(_concept("One-owner idea", record_count=1)),
        )


@pytest.mark.parametrize(
    ("label", "status"),
    (
        ("Active alias", "active"),
        ("Candidate concept", "candidate"),
        ("Inactive concept", "inactive"),
        ("Merged concept", "merged"),
    ),
)
def test_every_lifecycle_state_is_searched_before_candidate_creation(
    label: str,
    status: str,
) -> None:
    original = _catalogue()

    updated, report = REGISTER.prepare_registration(
        original,
        _manifest(_concept(label)),
    )

    result = report["results"][0]
    assert updated == original
    assert result["outcome"] == "existing_lifecycle_record"
    assert result["existing"]["status"] == status


def test_frequency_never_promotes_a_corpus_candidate() -> None:
    updated, report = REGISTER.prepare_registration(
        _catalogue(),
        _manifest(_concept("Large coherent cohort", record_count=60)),
    )

    result = report["results"][0]
    assert result["soft_frequency_signal"] == "above_soft_range"
    created = next(tag for tag in updated["tags"] if tag["id"] == "tag_0005")
    assert created["status"] == "candidate"


def test_cli_apply_requires_persisted_global_audit(tmp_path: Path) -> None:
    catalogue = tmp_path / "owner-tags.json"
    manifest = tmp_path / "manifest.json"
    catalogue.write_text(json.dumps(_catalogue()), encoding="utf-8")
    manifest.write_text(
        json.dumps(_manifest(_concept("Audited corpus concept"))),
        encoding="utf-8",
    )
    before = catalogue.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(manifest),
            "--catalogue",
            str(catalogue),
            "--apply",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--apply requires --audit" in result.stderr
    assert catalogue.read_bytes() == before
