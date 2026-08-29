from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.owner_tags import load_tag_targets
from src.tags import load_tag_catalogue


def _dossier(
    person_id: int,
    *,
    name: str = "Luxury brands",
    schema_version: int = 8,
    record_type: str = "person",
    research_status: str = "complete",
    review_status: str = "complete",
) -> dict:
    return {
        "schema_version": schema_version,
        "record_type": record_type,
        "research_status": research_status,
        "owner": {
            "person_id": person_id,
            "display_name": f"Owner {person_id}",
        },
        "review": {"status": review_status},
        "proposed_tags": [
            {
                "tag_id": None,
                "name": name,
                "summary": "Material association.",
                "confidence": 90,
                "source_ids": ["S1"],
            }
        ],
    }


def _write(directory: Path, person_id: int, document: dict) -> Path:
    path = directory / f"{person_id}.research.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_load_targets_resolves_dossier_aliases_to_canonical_names(
    tmp_path: Path,
) -> None:
    _write(tmp_path, 2, _dossier(2))
    _write(tmp_path, 1, _dossier(1, name="Video games"))

    targets, skipped = load_tag_targets(tmp_path, load_tag_catalogue())

    assert skipped == []
    assert [target["person_id"] for target in targets] == [1, 2]
    assert targets[1]["desired_tags"] == [
        {"id": "tag_0230", "name": "Luxury goods"}
    ]


def test_load_targets_skips_unusable_dossiers_instead_of_clearing_tags(
    tmp_path: Path,
) -> None:
    dossier = _dossier(
        3,
        record_type="unresolved_placeholder",
        research_status="identity_conflict",
    )
    dossier["proposed_tags"] = []
    _write(tmp_path, 3, dossier)

    targets, skipped = load_tag_targets(tmp_path, load_tag_catalogue())

    assert targets == []
    assert skipped[0]["person_id"] == 3
    assert "not safe" in skipped[0]["reason"]


def test_load_targets_rejects_pre_backfill_schema(tmp_path: Path) -> None:
    _write(tmp_path, 4, _dossier(4, schema_version=7))

    with pytest.raises(ValueError, match="schema v8"):
        load_tag_targets(tmp_path, load_tag_catalogue())


def test_load_targets_requires_every_requested_person_id(tmp_path: Path) -> None:
    _write(tmp_path, 5, _dossier(5))

    with pytest.raises(ValueError, match="requested person IDs: 6"):
        load_tag_targets(
            tmp_path,
            load_tag_catalogue(),
            person_ids={5, 6},
        )


def test_load_targets_reports_stale_tag_dossier_without_data_loss(
    tmp_path: Path,
) -> None:
    dossier = _dossier(7)
    dossier["proposed_tags"][0].update(
        {"tag_id": "tag_removed", "name": "Removed tag"}
    )
    _write(tmp_path, 7, dossier)

    targets, skipped = load_tag_targets(tmp_path, load_tag_catalogue())

    assert skipped == []
    assert targets[0]["desired_tags"] == []
    assert targets[0]["production_ready"] is False
    assert targets[0]["replacement_safe"] is False
    assert targets[0]["non_active_tag_references"][0]["status"] == "unknown"


def test_schema_v9_is_not_an_owner_tag_reconciliation_input(
    tmp_path: Path,
) -> None:
    dossier = _dossier(8, name="Video games", schema_version=9)
    _write(tmp_path, 8, dossier)

    with pytest.raises(ValueError, match="migrate it to schema v8"):
        load_tag_targets(tmp_path, load_tag_catalogue())
