from __future__ import annotations

import importlib.util
import json
import subprocess
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
    / "add_catalogue_tag.py"
)


def _load_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "add_catalogue_tag",
        SCRIPT_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


ADD_TAG = _load_module()


def _tag(tag_id: str, name: str, *, aliases: list[str] | None = None) -> dict:
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": aliases or [],
        "facets": ["sport"],
        "merged_into": None,
    }


def _document() -> dict:
    return {
        "schema_version": 1,
        "tags": [
            _tag("tag_0002", "Formula 1", aliases=["F1"]),
            _tag("tag_0007", "Tennis"),
        ],
    }


def test_existing_alias_is_reused_without_creating_an_id() -> None:
    updated, result = ADD_TAG.prepare_addition(
        _document(),
        name="F1",
        aliases=[],
        facets=["sport"],
    )

    assert updated is None
    assert result == {
        "id": "tag_0002",
        "name": "Formula 1",
        "status": "existing",
    }


def test_new_tag_gets_next_monotonic_id_and_is_sorted() -> None:
    updated, result = ADD_TAG.prepare_addition(
        _document(),
        name="Luxury goods",
        aliases=["Luxury brands"],
        facets=["subindustry", "parent:fashion_retail", "luxury"],
    )

    assert updated is not None
    assert result["id"] == "tag_0008"
    assert [tag["name"] for tag in updated["tags"]] == [
        "Formula 1",
        "Luxury goods",
        "Tennis",
    ]


def test_subindustry_requires_parent_classification() -> None:
    with pytest.raises(ValueError, match="require at least one parent"):
        ADD_TAG.prepare_addition(
            _document(),
            name="Luxury goods",
            aliases=[],
            facets=["subindustry", "luxury"],
        )


def test_semantic_alias_is_added_to_existing_canonical_tag() -> None:
    updated, result = ADD_TAG.prepare_alias_addition(
        _document(),
        canonical_label="Formula 1",
        alias="Grand Prix racing",
    )

    assert updated is not None
    assert result == {
        "id": "tag_0002",
        "name": "Formula 1",
        "alias": "Grand Prix racing",
        "status": "alias_added",
    }
    assert updated["tags"][0]["aliases"] == ["F1", "Grand Prix racing"]


def test_semantic_alias_cannot_collide_with_another_tag() -> None:
    with pytest.raises(ValueError, match="resolves to tag_0007"):
        ADD_TAG.prepare_alias_addition(
            _document(),
            canonical_label="Formula 1",
            alias="Tennis",
        )


def test_candidate_requires_exactly_one_type_facet() -> None:
    with pytest.raises(ValueError, match="exactly one tag type"):
        ADD_TAG.prepare_addition(
            _document(),
            name="Luxury goods",
            aliases=[],
            facets=["subindustry", "occupation", "parent:fashion_retail"],
        )


def test_cli_apply_writes_valid_catalogue_atomically(tmp_path: Path) -> None:
    catalogue_path = tmp_path / "owner-tags.json"
    catalogue_path.write_text(
        json.dumps(_document(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--catalogue",
            str(catalogue_path),
            "--name",
            "Luxury goods",
            "--alias",
            "Luxury brands",
            "--facet",
            "subindustry",
            "--facet",
            "parent:fashion_retail",
            "--apply",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    updated = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert [tag["name"] for tag in updated["tags"]] == [
        "Formula 1",
        "Luxury goods",
        "Tennis",
    ]
    assert updated["tags"][1]["id"] == "tag_0008"
