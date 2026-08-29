from __future__ import annotations

from collections import Counter

from src.diffing import build_tag_change_plan
from src.tags import load_tag_catalogue
from update_owner_tags import (
    _verification_succeeded,
    build_offline_publication_record,
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
        owner_counts=Counter({"tag_0205": 1}),
        minimum_owner_count=2,
    )

    assert plan["additions"] == []
    assert plan["removals"] == []
    assert plan["has_changes"] is False
    assert plan["suppressed_additions"] == [
        {"id": "tag_0205", "name": "Gambling", "owner_count": 1}
    ]


def test_tag_supported_by_two_owners_remains_publishable() -> None:
    plan = build_tag_change_plan(
        person_id=1,
        desired_names=["Gambling"],
        live_tags=[],
        catalogue=load_tag_catalogue(),
    )

    suppress_low_frequency_additions(
        plan,
        owner_counts=Counter({"tag_0205": 2}),
        minimum_owner_count=2,
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
        owner_counts=Counter({"tag_0205": 1}),
        minimum_owner_count=2,
    )

    assert plan["additions"] == []
    assert plan["removals"] == []
    assert plan["alias_replacements"] == []
    assert plan["has_changes"] is False


def test_offline_manifest_separates_publishable_and_singleton_tags() -> None:
    target = {
        "person_id": 1,
        "display_name": "Example Owner",
        "desired_tags": [
            {"id": "tag_0205", "name": "Gambling"},
            {"id": "tag_0213", "name": "Casino operations"},
        ],
    }

    record = build_offline_publication_record(
        target,
        owner_counts=Counter({"tag_0205": 2, "tag_0213": 1}),
        minimum_owner_count=2,
    )

    assert record["status"] == "offline_manifest"
    assert record["live_comparison_performed"] is False
    assert record["operations"] == []
    assert record["plan"]["additions"] is None
    assert record["plan"]["removals"] is None
    assert record["plan"]["publishable_desired_tags"] == [
        {"id": "tag_0205", "name": "Gambling", "owner_count": 2}
    ]
    assert record["plan"]["suppressed_additions"] == [
        {"id": "tag_0213", "name": "Casino operations", "owner_count": 1}
    ]
