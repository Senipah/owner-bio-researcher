from __future__ import annotations

from copy import deepcopy

import pytest

from src.tags import (
    FORBIDDEN_CANONICAL_TAGS,
    TagCatalogue,
    TagResolutionError,
    load_tag_catalogue,
    normalize_tag_name,
    resolve_dossier_tags,
)


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
        "facets": ["test"],
        "merged_into": merged_into,
    }


def _proposal(name: str, tag_id: str | None = None) -> dict:
    return {
        "tag_id": tag_id,
        "name": name,
        "summary": "A durable material association is supported.",
        "confidence": {
            "score": 95,
            "band": "very_high",
            "reason": "Official evidence supports the association.",
        },
        "source_ids": ["S1"],
    }


def test_seed_catalogue_contains_complete_supported_long_tail() -> None:
    catalogue = load_tag_catalogue()

    assert len(catalogue.tags_by_id) == 199
    assert sum(
        "business family" in tag.facets
        for tag in catalogue.tags_by_id.values()
    ) == 45
    assert sum(
        "royal family" in tag.facets
        for tag in catalogue.tags_by_id.values()
    ) == 8
    for name in (
        "Al Bu Said",
        "Alaouite dynasty",
        "Norwegian royal family",
        "Boxing",
        "Apple",
        "Murdoch family",
        "Ofer family",
        "Gucci family",
        "Della Valle family",
        "Haji-Ioannou family",
        "Aston Martin",
        "Gambling",
        "eBay",
        "Pirelli",
        "easyJet",
        "Valve",
        "Celebrity Cruises",
        "Tod's",
    ):
        assert catalogue.resolve(tag_id=None, name=name).name == name
    assert not (
        FORBIDDEN_CANONICAL_TAGS
        & {tag.normalized_name for tag in catalogue.tags_by_id.values()}
    )
    assert not {
        label: ids
        for label, ids in catalogue.lookup.items()
        if len({catalogue._terminal_tag(tag_id).id for tag_id in ids}) > 1
    }


def test_gaming_means_gambling_and_video_games_requires_its_explicit_name() -> None:
    catalogue = load_tag_catalogue()

    assert catalogue.resolve(tag_id=None, name="Gaming").name == "Gambling"
    assert catalogue.resolve(tag_id=None, name="Gambling & Casinos").name == (
        "Gambling"
    )
    assert catalogue.resolve(tag_id=None, name="Video games").name == "Video games"


def test_generic_philanthropy_and_family_office_tags_are_removed() -> None:
    catalogue = load_tag_catalogue()

    for name in (
        "Arts & culture philanthropy",
        "Children & youth philanthropy",
        "Education philanthropy",
        "Family office",
        "Health philanthropy",
        "Science philanthropy",
    ):
        with pytest.raises(TagResolutionError, match="unknown tag name"):
            catalogue.resolve(tag_id=None, name=name)

    assert catalogue.resolve(tag_id=None, name="Humanitarian aid").name == (
        "Humanitarian aid"
    )
    assert catalogue.resolve(
        tag_id=None,
        name="Marine / ocean conservation",
    ).name == "Marine / ocean conservation"


def test_aliases_share_the_canonical_normalization_path() -> None:
    catalogue = load_tag_catalogue()

    formula = catalogue.resolve(tag_id=None, name="Formula_1")
    assert formula == catalogue.resolve(tag_id=None, name="F1")
    assert formula.name == "Formula 1"
    assert catalogue.resolve(tag_id=None, name="Yildirim family").name == (
        "Yıldırım family"
    )


def test_resolution_follows_merged_into_for_id_and_alias() -> None:
    catalogue = TagCatalogue(
        {
            "schema_version": 1,
            "tags": [
                _tag("tag_old", "Formula One legacy", aliases=["F1"], merged_into="tag_new"),
                _tag("tag_new", "Formula 1"),
            ],
        }
    )

    assert catalogue.resolve(tag_id="tag_old", name="F1").id == "tag_new"
    assert catalogue.resolve(tag_id=None, name="F1").id == "tag_new"


def test_unknown_and_ambiguous_names_are_explicit_errors() -> None:
    catalogue = TagCatalogue(
        {
            "schema_version": 1,
            "tags": [
                _tag("tag_a", "Alpha", aliases=["Shared"]),
                _tag("tag_b", "Beta", aliases=["Shared"]),
            ],
        }
    )

    with pytest.raises(TagResolutionError, match="unknown tag name 'Missing'"):
        catalogue.resolve(tag_id=None, name="Missing")
    with pytest.raises(TagResolutionError, match="ambiguous tag name 'Shared'"):
        catalogue.resolve(tag_id=None, name="Shared")


def test_dossier_resolution_rejects_alias_duplicates_after_canonicalization() -> None:
    catalogue = load_tag_catalogue()
    dossier = {
        "proposed_tags": [
            _proposal("F1"),
            _proposal("Formula One"),
        ]
    }

    with pytest.raises(TagResolutionError, match="duplicate canonical tag"):
        resolve_dossier_tags(dossier, catalogue, person_id=10)


def test_tag_id_is_authoritative_and_name_must_match_it() -> None:
    catalogue = load_tag_catalogue()
    apple = catalogue.resolve(tag_id=None, name="Apple")
    proposal = _proposal("Microsoft", tag_id=apple.id)

    with pytest.raises(TagResolutionError, match="does not match name"):
        resolve_dossier_tags(
            {"proposed_tags": [deepcopy(proposal)]},
            catalogue,
            person_id=10,
        )
