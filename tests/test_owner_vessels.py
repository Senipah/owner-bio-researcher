from __future__ import annotations

from pathlib import Path

from src.owner_vessels import (
    apply_owner_vessel_ranking,
    current_vessel_references,
    sort_and_rank_owners,
)
from src.parsers import (
    normalize_gross_tonnage,
    normalize_loa_metres,
    parse_owner_vessel_relationships,
    parse_vessel_specification,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples"


def _relationship(
    vessel_id: int,
    name: str,
    *,
    current: bool = True,
    relationship_id: int | None = None,
) -> dict:
    return {
        "relationship_id": relationship_id,
        "vessel_id": vessel_id,
        "vessel_name": name,
        "specification_url": f"https://example.test/vessel?id={vessel_id}",
        "from": "Jan 2020",
        "to": "" if current else "Feb 2021",
        "is_current": current,
    }


def _owner(person_id: int, relationships: list[dict]) -> dict:
    return {
        "person_id": person_id,
        "vessel_ownership": {
            "status": "ok",
            "relationships": relationships,
        },
    }


def _spec(vessel_id: int, loa_m: float | None, *, status: str = "ok") -> dict:
    return {
        "vessel_id": vessel_id,
        "vessel_name": f"Vessel {vessel_id}",
        "specification_url": f"https://example.test/vessel?id={vessel_id}",
        "loa_raw": f"{loa_m}m" if loa_m is not None else "",
        "loa_m": loa_m,
        "gross_tonnage_raw": "",
        "gross_tonnage": None,
        "status": status,
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "error": None if status == "ok" else "failed",
    }


def test_loa_normalization_supports_metric_and_imperial_values() -> None:
    assert normalize_loa_metres("180.65m") == 180.65
    assert normalize_loa_metres("180,65 metres") == 180.65
    assert normalize_loa_metres("300 ft") == 91.44
    assert normalize_loa_metres("100' 6\"") == 30.632
    assert normalize_loa_metres("100′ 6″") == 30.632
    assert normalize_loa_metres("-") is None
    assert normalize_loa_metres("unknown") is None


def test_gross_tonnage_normalization_is_optional() -> None:
    assert normalize_gross_tonnage("13,136 tonnes") == 13136
    assert normalize_gross_tonnage("1234.5 GT") == 1234.5
    assert normalize_gross_tonnage("-") is None


def test_owner_fixture_extracts_current_vessel_relationship() -> None:
    path = FIXTURES / "person-page" / "Aaron Fidler _ Owners Edit.html"
    page_url = (
        "https://agent.superyachtnetwork.com/"
        "yaycontact/vessel/owners/person/detail.htm?id=8690"
    )
    relationships = parse_owner_vessel_relationships(
        path.read_text(encoding="utf-8"),
        page_url=page_url,
    )

    assert relationships == [
        {
            "relationship_id": 5891,
            "vessel_id": 24371,
            "vessel_name": "AK Royalty",
            "specification_url": (
                "https://agent.superyachtnetwork.com/vessel/view.htm?id=24371"
            ),
            "from": "Sep 2022",
            "to": "",
            "is_current": True,
        }
    ]


def test_vessel_fixture_extracts_loa_and_gross_tonnage() -> None:
    path = (
        FIXTURES
        / "top-100"
        / "vessel-page"
        / "YachtCast - Yacht Details.html"
    )
    specification = parse_vessel_specification(
        path.read_text(encoding="utf-8")
    )

    assert specification == {
        "loa_raw": "180.65m",
        "loa_m": 180.65,
        "gross_tonnage_raw": "13,136 tonnes",
        "gross_tonnage": 13136,
    }


def test_ranking_deduplicates_vessels_and_uses_largest_known_loa() -> None:
    owner = _owner(
        10,
        [
            _relationship(1, "Small", relationship_id=100),
            _relationship(1, "Small", relationship_id=101),
            _relationship(2, "Large", relationship_id=102),
            _relationship(3, "Historic", current=False, relationship_id=103),
        ],
    )
    specs = {"1": _spec(1, 30.0), "2": _spec(2, 60.0)}

    assert set(current_vessel_references([owner])) == {1, 2}
    apply_owner_vessel_ranking(owner, specs)

    ownership = owner["vessel_ownership"]
    assert ownership["ranking_status"] == "ranked"
    assert len(ownership["current_vessels"]) == 2
    assert ownership["largest_current_loa_m"] == 60.0
    assert (
        ownership["largest_known_current_vessel"]["vessel_name"] == "Large"
    )


def test_incomplete_specs_do_not_claim_a_fully_ranked_owner() -> None:
    owner = _owner(
        10,
        [
            _relationship(1, "Known"),
            _relationship(2, "Unknown"),
        ],
    )
    apply_owner_vessel_ranking(owner, {"1": _spec(1, 40.0)})

    ownership = owner["vessel_ownership"]
    assert ownership["ranking_status"] == "incomplete"
    assert ownership["largest_current_loa_m"] == 40.0
    assert (
        ownership["largest_known_current_vessel"]["vessel_name"] == "Known"
    )


def test_sort_assigns_descending_loa_rank_and_keeps_unranked_last() -> None:
    small = _owner(1, [_relationship(1, "Small")])
    large = _owner(2, [_relationship(2, "Large")])
    none = _owner(3, [])
    large_co_owner = _owner(4, [_relationship(2, "Large")])
    specs = {"1": _spec(1, 30.0), "2": _spec(2, 60.0)}
    for owner in (small, large, large_co_owner, none):
        apply_owner_vessel_ranking(owner, specs)
    document = {"owners": [small, none, large_co_owner, large]}

    sort_and_rank_owners(document)

    assert [owner["person_id"] for owner in document["owners"]] == [2, 4, 1, 3]
    assert large["vessel_ownership"]["loa_rank"] == 1
    assert large_co_owner["vessel_ownership"]["loa_rank"] == 1
    assert small["vessel_ownership"]["loa_rank"] == 2
    assert none["vessel_ownership"]["loa_rank"] is None
