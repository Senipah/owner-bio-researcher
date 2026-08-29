from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from src.diffing import build_tag_change_plan
from src.tags import load_tag_catalogue
from update_owner_tags import (
    _verification_succeeded,
    build_offline_review_record,
    load_reviewed_removal_manifest,
    protect_non_production_target,
    suppress_low_frequency_additions,
)


def _plan(*, additions: int = 0, removals: int = 0, conflicts: int = 0) -> dict:
    return {
        "additions": [{} for _ in range(additions)],
        "removals": [{} for _ in range(removals)],
        "conflicts": [{} for _ in range(conflicts)],
    }


def test_add_only_verification_allows_unremoved_live_extras() -> None:
    assert _verification_succeeded(
        _plan(removals=1),
        replace_tags=False,
    )


def test_exact_verification_requires_removals_to_be_complete() -> None:
    assert not _verification_succeeded(
        _plan(removals=1),
        replace_tags=True,
    )


def test_verification_never_accepts_missing_additions_or_conflicts() -> None:
    assert not _verification_succeeded(
        _plan(additions=1),
        replace_tags=False,
    )
    assert not _verification_succeeded(
        _plan(conflicts=1),
        replace_tags=False,
    )


def test_low_frequency_new_tag_addition_is_suppressed() -> None:
    plan = build_tag_change_plan(
        person_id=1,
        desired_names=["Gambling"],
        live_tags=[],
        catalogue=load_tag_catalogue(),
    )

    suppress_low_frequency_additions(
        plan,
        dossier_record_counts=Counter({"tag_0205": 1}),
        minimum_dossier_record_count=2,
    )

    assert plan["additions"] == []
    assert plan["removals"] == []
    assert plan["has_changes"] is False
    assert plan["suppressed_additions"] == [
        {"id": "tag_0205", "name": "Gambling", "dossier_record_count": 1}
    ]


def test_tag_supported_by_two_records_remains_frequency_eligible_only() -> None:
    plan = build_tag_change_plan(
        person_id=1,
        desired_names=["Gambling"],
        live_tags=[],
        catalogue=load_tag_catalogue(),
    )

    suppress_low_frequency_additions(
        plan,
        dossier_record_counts=Counter({"tag_0205": 2}),
        minimum_dossier_record_count=2,
    )

    assert plan["additions"] == [{"id": "tag_0205", "name": "Gambling"}]
    assert plan["suppressed_additions"] == []


def test_low_frequency_alias_replacement_is_deferred_without_deletion() -> None:
    plan = build_tag_change_plan(
        person_id=1,
        desired_names=["Gambling"],
        live_tags=[{"association_id": "7", "name": "Gaming"}],
        catalogue=load_tag_catalogue(),
    )
    assert plan["additions"]
    assert plan["removals"]

    suppress_low_frequency_additions(
        plan,
        dossier_record_counts=Counter({"tag_0205": 1}),
        minimum_dossier_record_count=2,
    )

    assert plan["additions"] == []
    assert plan["removals"] == []
    assert plan["alias_replacements"] == []
    assert plan["has_changes"] is False


def test_offline_manifest_reports_frequency_without_approval_or_live_diff() -> None:
    target = {
        "person_id": 1,
        "display_name": "Example Owner",
        "desired_tags": [
            {"id": "tag_0205", "name": "Gambling"},
            {"id": "tag_0213", "name": "Casino operations"},
        ],
    }

    record = build_offline_review_record(
        target,
        dossier_record_counts=Counter({"tag_0205": 2, "tag_0213": 1}),
        minimum_dossier_record_count=2,
    )

    assert record["status"] == "offline_manifest"
    assert record["live_comparison_performed"] is False
    assert record["operations"] == []
    assert record["plan"]["additions"] is None
    assert record["plan"]["removals"] is None
    assert record["plan"]["frequency_eligible_active_assignments"] == [
        {"id": "tag_0205", "name": "Gambling", "dossier_record_count": 2}
    ]
    assert record["plan"]["below_addition_threshold_assignments"] == [
        {
            "id": "tag_0213",
            "name": "Casino operations",
            "dossier_record_count": 1,
        }
    ]
    assert "approval" in record["plan"]["note"]


def test_incomplete_legacy_target_cannot_authorize_removals() -> None:
    plan = {
        "additions": [{"id": "tag_0205", "name": "Gambling"}],
        "removals": [{"association_id": "11", "name": "Legacy tag"}],
        "alias_replacements": [],
        "has_changes": True,
        "is_exact": False,
    }

    protect_non_production_target(plan, {"replacement_safe": False})

    assert plan["additions"] == [{"id": "tag_0205", "name": "Gambling"}]
    assert plan["removals"] == []
    assert plan["blocked_removals"] == [
        {"association_id": "11", "name": "Legacy tag"}
    ]


def test_removal_manifest_requires_a_successful_live_dry_run(
    tmp_path: Path,
) -> None:
    dossier_directory = tmp_path / "dossiers"
    dossier_directory.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "mode": "offline-dry-run",
                "live_read_performed": False,
                "dossier_directory": str(dossier_directory),
                "tag_catalogue": "config/owner-tags.json",
                "minimum_dossier_record_count_for_new_additions": 2,
                "records": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        load_reviewed_removal_manifest(
            manifest,
            dossier_directory=dossier_directory,
            catalogue_source="config/owner-tags.json",
            minimum_dossier_record_count=2,
        )
    except ValueError as exc:
        assert "live dry-run" in str(exc)
    else:
        raise AssertionError("offline report must not authorize removals")
