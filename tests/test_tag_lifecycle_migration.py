from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from src.tags import TagCatalogue, TagResolutionError, normalize_tag_name


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "migrate_tag_catalogue_lifecycle.py"
)


def _load_module() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "migrate_tag_catalogue_lifecycle",
        SCRIPT_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


MIGRATE = _load_module()


def _tag(
    tag_id: str,
    name: str,
    *,
    aliases: list[str] | None = None,
    merged_into: str | None = None,
) -> dict:
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": aliases or [],
        "facets": ["occupation"],
        "merged_into": merged_into,
    }


def test_lifecycle_migration_preserves_ids_and_does_not_promote_frequency() -> None:
    baseline = {
        "schema_version": 1,
        "tags": [_tag("tag_0001", "Approved", aliases=["Old alias"])],
    }
    current = {
        "schema_version": 1,
        "tags": [
            _tag(
                "tag_0001",
                "Approved",
                aliases=["Old alias", "Unreviewed alias"],
            ),
            _tag("tag_0002", "Seen twice"),
            _tag("tag_0003", "Seen once"),
            _tag("tag_0004", "Merged legacy", merged_into="tag_0001"),
        ],
    }
    audit = {
        "records": [
            {
                "desired_tags": [
                    {"id": "tag_0002"},
                    {"id": "tag_0003"},
                ]
            },
            {"desired_tags": [{"id": "tag_0002"}]},
        ]
    }

    migrated, report = MIGRATE.prepare_migration(
        current,
        baseline,
        audit,
        baseline_ref="approved-ref",
        source_run="runaway-ref",
        audit_reference="diagnostic.json",
    )
    catalogue = TagCatalogue(migrated)

    assert set(catalogue.all_tags_by_id) == {
        "tag_0001",
        "tag_0002",
        "tag_0003",
        "tag_0004",
    }
    assert set(catalogue.tags_by_id) == {"tag_0001"}
    assert catalogue.all_tags_by_id["tag_0002"].status == "candidate"
    assert catalogue.all_tags_by_id["tag_0003"].status == "inactive"
    assert catalogue.resolve(tag_id="tag_0004", name="Merged legacy").id == (
        "tag_0001"
    )
    assert catalogue.inspect(tag_id=None, name="Unreviewed alias")["status"] == (
        "unknown"
    )
    assert catalogue.all_tags_by_id["tag_0001"].lifecycle[
        "pending_aliases"
    ] == ["Unreviewed alias"]
    try:
        catalogue.resolve(tag_id=None, name="Seen twice")
    except TagResolutionError as exc:
        assert "non-assignable" in str(exc)
    else:
        raise AssertionError("record frequency must not activate a candidate")
    assert report["stable_ids_preserved"] is True
    assert report["lifecycle_counts"] == {
        "active": 1,
        "candidate": 1,
        "inactive": 1,
        "merged": 1,
    }
    assert report["dossiers_modified"] == 0
    assert report["live_state_modified"] is False
