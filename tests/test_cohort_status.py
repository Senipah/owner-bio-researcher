from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.cohort_status import (
    load_researched_owner_ids,
    load_updated_owner_ids,
    prepare_cohort_status_sync,
)


def _cohort() -> dict:
    return {
        "schema_version": 1,
        "selection": "all-by-loa",
        "cohort_size": 3,
        "owners": [
            {"cohort_position": 1, "person_id": 10, "display_name": "Ten"},
            {"cohort_position": 2, "person_id": 20, "display_name": "Twenty"},
            {"cohort_position": 3, "person_id": 30, "display_name": "Thirty"},
        ],
    }


def test_prepare_sync_adds_exact_status_and_summary() -> None:
    updated, report = prepare_cohort_status_sync(
        _cohort(),
        researched_owner_ids={10, 20},
        imported_updated_owner_ids={10},
    )

    assert [owner["workflow"] for owner in updated["owners"]] == [
        {"researched": True, "updated_in_system": True},
        {"researched": True, "updated_in_system": False},
        {"researched": False, "updated_in_system": False},
    ]
    assert updated["workflow_summary"] == {
        "completed_prefix": 2,
        "researched_count": 2,
        "updated_in_system_count": 1,
        "remaining_research_count": 1,
        "next_unresearched_owner": {
            "cohort_position": 3,
            "person_id": 30,
            "display_name": "Thirty",
            "largest_current_vessel_name": None,
            "largest_current_loa_m": None,
        },
    }
    assert report["completed_prefix"] == 2
    assert report["next_unresearched_owner"]["person_id"] == 30
    assert report["cohort_changed"] is True
    assert report["workflow_summary_changed"] is True
    assert report["changed_owner_count"] == 3


def test_import_is_monotonic_and_explicit_reset_is_supported() -> None:
    first, _ = prepare_cohort_status_sync(
        _cohort(),
        researched_owner_ids={10, 20},
        imported_updated_owner_ids={10},
    )
    second, _ = prepare_cohort_status_sync(
        first,
        researched_owner_ids={10, 20},
        imported_updated_owner_ids=set(),
        mark_not_updated_owner_ids={10},
        mark_updated_owner_ids={20},
    )

    assert second["owners"][0]["workflow"]["updated_in_system"] is False
    assert second["owners"][1]["workflow"]["updated_in_system"] is True


def test_sync_is_idempotent() -> None:
    first, _ = prepare_cohort_status_sync(
        _cohort(),
        researched_owner_ids={10, 20},
        imported_updated_owner_ids={10},
    )
    second, report = prepare_cohort_status_sync(
        first,
        researched_owner_ids={10, 20},
        imported_updated_owner_ids=set(),
    )

    assert second == first
    assert report["cohort_changed"] is False
    assert report["workflow_summary_changed"] is False
    assert report["changed_owner_count"] == 0
    assert report["changed_person_ids"] == []


def test_sync_counts_a_missing_workflow_key_as_a_change() -> None:
    cohort = _cohort()
    cohort["owners"][2]["workflow"] = {"researched": False}

    updated, report = prepare_cohort_status_sync(
        cohort,
        researched_owner_ids=set(),
        imported_updated_owner_ids=set(),
    )

    assert updated["owners"][2]["workflow"] == {
        "researched": False,
        "updated_in_system": False,
    }
    assert report["changed_owner_count"] == 3


def test_updated_owner_must_be_researched() -> None:
    with pytest.raises(ValueError, match="must also be researched"):
        prepare_cohort_status_sync(
            _cohort(),
            researched_owner_ids={10},
            imported_updated_owner_ids={20},
        )


def test_researched_owners_must_form_a_contiguous_prefix() -> None:
    with pytest.raises(ValueError, match="contiguous cohort prefix"):
        prepare_cohort_status_sync(
            _cohort(),
            researched_owner_ids={10, 30},
            imported_updated_owner_ids=set(),
        )


def test_completed_cohort_has_no_next_owner() -> None:
    updated, report = prepare_cohort_status_sync(
        _cohort(),
        researched_owner_ids={10, 20, 30},
        imported_updated_owner_ids=set(),
    )

    assert updated["workflow_summary"]["completed_prefix"] == 3
    assert updated["workflow_summary"]["remaining_research_count"] == 0
    assert updated["workflow_summary"]["next_unresearched_owner"] is None
    assert report["next_unresearched_owner"] is None


def test_load_status_sources(tmp_path: Path) -> None:
    dossier_dir = tmp_path / "dossiers"
    dossier_dir.mkdir()
    (dossier_dir / "10.research.json").write_text(
        json.dumps(
            {
                "owner": {"person_id": 10},
                "review": {"status": "complete"},
            }
        ),
        encoding="utf-8",
    )
    (dossier_dir / "20.research.json").write_text(
        json.dumps(
            {
                "owner": {"person_id": 20},
                "review": {"status": "pending"},
            }
        ),
        encoding="utf-8",
    )
    owner_input = tmp_path / "owners.json"
    owner_input.write_text(
        json.dumps(
            {
                "owners": [
                    {
                        "person_id": 10,
                        "workflow": {"updated_in_system": True},
                    },
                    {
                        "person_id": 20,
                        "workflow": {"updated_in_system": False},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_researched_owner_ids(dossier_dir) == {10}
    assert load_updated_owner_ids([owner_input]) == {10}
