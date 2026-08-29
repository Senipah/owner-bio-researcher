from __future__ import annotations

from copy import deepcopy

from src.tag_diagnostics import build_tag_governance_diagnostics
from src.tags import TagCatalogue, normalize_tag_name


def _tag(tag_id: str, name: str, facets: list[str]) -> dict:
    return {
        "id": tag_id,
        "name": name,
        "normalized_name": normalize_tag_name(name),
        "aliases": [],
        "facets": facets,
        "status": "active",
        "merged_into": None,
        "lifecycle": {},
    }


def test_diagnostics_are_warnings_and_never_edit_inputs() -> None:
    catalogue = TagCatalogue(
        {
            "schema_version": 2,
            "tags": [
                _tag("tag_1", "Alpha profession", ["occupation"]),
                _tag("tag_2", "Beta profession", ["occupation"]),
                _tag("tag_3", "Gamma profession", ["occupation"]),
                _tag("tag_4", "Career transition after expansion", ["occupation"]),
            ],
        }
    )
    targets = [
        {
            "person_id": 10,
            "display_name": "Same Name",
            "desired_tags": [
                {"id": "tag_1", "name": "Alpha profession"},
                {"id": "tag_2", "name": "Beta profession"},
                {"id": "tag_3", "name": "Gamma profession"},
            ],
            "candidate_concepts": [
                {"proposed_name": "Alpha profession"}
            ],
            "non_active_tag_references": [
                {"status": "inactive", "name": "Retired"}
            ],
        },
        {
            "person_id": 11,
            "display_name": "Same Name",
            "desired_tags": [{"id": "tag_1", "name": "Alpha profession"}],
            "candidate_concepts": [],
            "non_active_tag_references": [],
        },
    ]
    original = deepcopy(targets)

    report = build_tag_governance_diagnostics(
        targets,
        catalogue,
        low_record_count=5,
        high_record_count=50,
        high_assignment_count=2,
    )

    assert targets == original
    assert report["mode"] == "diagnostic_warnings_only"
    assert report["automatic_edits"] is False
    assert report["soft_frequency_range"]["approval_effect"] == "none"
    assert report["count_semantics"] == (
        "source dossier records, not unique people"
    )
    assert report["high_assignment_records"][0]["person_id"] == 10
    assert report["semantic_dimension_overlaps"][0]["dimension"] == (
        "profession_or_role"
    )
    assert report["candidate_concepts_matching_active_labels"][0][
        "active_tag"
    ]["id"] == "tag_1"
    assert report["non_active_dossier_references"][0]["status"] == "inactive"
    assert report["sentence_or_transition_style_names"][0]["tag_id"] == (
        "tag_4"
    )


def test_matching_names_and_birth_dates_do_not_collapse_record_counts() -> None:
    catalogue = TagCatalogue(
        {"schema_version": 2, "tags": [_tag("tag_1", "Shared", ["sport"])]}
    )
    targets = [
        {
            "person_id": 101,
            "display_name": "Alex Example",
            "date_of_birth": "1970-01-01",
            "desired_tags": [{"id": "tag_1", "name": "Shared"}],
        },
        {
            "person_id": 202,
            "display_name": "Alex Example",
            "date_of_birth": "1970-01-01",
            "desired_tags": [{"id": "tag_1", "name": "Shared"}],
        },
    ]

    report = build_tag_governance_diagnostics(targets, catalogue)
    warning = next(
        item
        for item in report["active_frequency_outliers"]
        if item["tag_id"] == "tag_1"
    )

    assert warning["dossier_record_count"] == 2
