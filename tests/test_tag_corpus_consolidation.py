from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "consolidate_owner_tag_corpus.py"
)
CONFIG = REPO_ROOT / "config" / "owner-tag-consolidation.json"
CATALOGUE = REPO_ROOT / "config" / "owner-tags.json"
DOSSIERS = REPO_ROOT / "output" / "owner-research" / "all-by-loa"


def _load_module():
    specification = importlib.util.spec_from_file_location(
        "consolidate_owner_tag_corpus", SCRIPT
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_manifest_is_repository_only_and_resolves_the_candidate_pool() -> None:
    module = _load_module()
    configuration = json.loads(CONFIG.read_text(encoding="utf-8"))
    document = json.loads(CATALOGUE.read_text(encoding="utf-8"))

    updated, report = module.prepare_catalogue(
        document,
        configuration,
        referenced_inactive_ids=set(),
    )

    assert configuration["repository_is_source_of_truth"] is True
    assert configuration["live_state_is_taxonomy_input"] is False
    assert report["lifecycle_counts_after"]["candidate"] == 0
    assert report["stable_id_count"] == len(document["tags"])
    active = [tag for tag in updated["tags"] if tag["status"] == "active"]
    assert report["active_contract_count"] == len(active)
    assert all(tag["semantic_contract"]["membership"] for tag in active)
    assert all(tag["semantic_contract"]["exclusions"] for tag in active)


def test_explicit_alias_decisions_are_applied_without_false_aliases() -> None:
    module = _load_module()
    configuration = json.loads(CONFIG.read_text(encoding="utf-8"))
    document = json.loads(CATALOGUE.read_text(encoding="utf-8"))

    updated, _ = module.prepare_catalogue(
        document,
        configuration,
        referenced_inactive_ids=set(),
    )
    by_id = {tag["id"]: tag for tag in updated["tags"]}

    assert "Hydrostroy AD" in by_id["tag_0094"]["aliases"]
    assert "Multi-brand restaurant group" in by_id["tag_0241"]["aliases"]
    assert "Winemaking business" in by_id["tag_0201"]["aliases"]
    assert "Disney Plus" not in by_id["tag_0055"]["aliases"]
    assert "Buyout investing" not in by_id["tag_0152"]["aliases"]
    assert "Wine" not in by_id["tag_0201"]["aliases"]


def test_unresolved_placeholder_is_byte_equivalent_in_preparation() -> None:
    module = _load_module()
    configuration = json.loads(CONFIG.read_text(encoding="utf-8"))
    document = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    updated_catalogue, _ = module.prepare_catalogue(
        document,
        configuration,
        referenced_inactive_ids=set(),
    )
    catalogue = module.TagCatalogue(updated_catalogue)
    unresolved_path = DOSSIERS / "911.research.json"
    unresolved = json.loads(unresolved_path.read_text(encoding="utf-8"))

    prepared, row = module._prepare_one_dossier(
        unresolved,
        None,
        catalogue,
        configuration,
    )

    assert prepared == unresolved
    assert row["status"] == "unresolved_preserved"
    assert row["after_ids"] == ["tag_0249"]


def test_granular_gambling_and_video_games_require_correct_umbrellas() -> None:
    configuration = json.loads(CONFIG.read_text(encoding="utf-8"))
    companions = configuration["required_companions"]

    for tag_id in (
        "tag_0212",
        "tag_0213",
        "tag_0225",
        "tag_0235",
        "tag_0250",
        "tag_0546",
        "tag_1982",
    ):
        assert "tag_0205" in companions[tag_id]
    assert companions["tag_0307"] == ["tag_0193"]
    assert companions["tag_0352"] == ["tag_0193"]
