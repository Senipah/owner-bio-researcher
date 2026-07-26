from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.top_100 import (
    parse_specification_edit_url,
    parse_top_100_list,
    parse_ubo_relationships,
    top_100_page_url,
)
from src.workflow import (
    annotate_top_100_owners,
    ensure_owner_workflow,
    mark_owner_details_enriched,
    mark_owner_updated_in_system,
    owner_matches_workflow,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "top-100"


def _owner(person_id: int, enrichment_status: str = "pending") -> dict:
    return {
        "person_id": person_id,
        "profile_url": f"https://example.test/owner?id={person_id}",
        "report": {},
        "details": {},
        "social_media_profiles": [],
        "_baseline": None,
        "enrichment": {
            "status": enrichment_status,
            "enriched_at": None,
            "error": None,
        },
    }


def _vessel(
    *,
    vessel_id: int,
    rank: int,
    name: str,
    relationships: list[dict],
) -> dict:
    return {
        "vessel_id": vessel_id,
        "rank": rank,
        "vessel_name": name,
        "ownership_scan": {"status": "ok"},
        "ubo_relationships": relationships,
    }


def _relationship(
    person_id: int,
    relationship_id: int,
    *,
    current: bool,
) -> dict:
    return {
        "owner_person_id": person_id,
        "relationship_id": relationship_id,
        "from": "Jan 2020",
        "to": "" if current else "Feb 2021",
        "status": "",
        "is_current": current,
    }


def test_top_100_list_fixture_extracts_all_columns_and_pagination() -> None:
    path = FIXTURES / "YB Fleet List.html"
    page_url = top_100_page_url(1)
    vessels, next_page, last_page = parse_top_100_list(
        path.read_text(encoding="utf-8"),
        page_url=page_url,
    )

    assert len(vessels) == 32
    assert next_page == 2
    assert last_page == 4
    first = vessels[0]
    assert first["rank"] == 1
    assert first["vessel_id"] == 40757
    assert first["vessel_name"] == "Azzam"
    assert first["builder_name"] == "Lurssen"
    assert len(first["report"]) == 29
    assert first["report"]["length"] == "181m"
    assert first["report"]["captains_cabin"] is True
    assert first["report"]["photo_overview"] is False
    assert first["report"]["photo_illustration"] is True


def test_page_url_always_preserves_top_100_filter() -> None:
    url = top_100_page_url(3)
    query = parse_qs(urlparse(url).query, keep_blank_values=True)

    assert query["page"] == ["3"]
    assert query["yb_100"] == ["t"]
    assert query["mode"] == ["listings"]
    assert "length_from" in query


def test_specification_and_edit_mode_fixtures_extract_ubo_links() -> None:
    view_path = (
        FIXTURES / "vessel-page" / "YachtCast - Yacht Details.html"
    )
    view_url = "https://agent.superyachtnetwork.com/vessel/view.htm?id=40757"
    edit_url = parse_specification_edit_url(
        view_path.read_text(encoding="utf-8"),
        page_url=view_url,
    )
    assert edit_url.endswith(
        "/vessel/edit/specification_new/edit.htm?id=40757"
    )

    edit_path = (
        FIXTURES / "vessel-page" / "edit-mode" / "YachtCast.html"
    )
    relationships = parse_ubo_relationships(
        edit_path.read_text(encoding="utf-8"),
        page_url=edit_url,
    )

    assert len(relationships) == 2
    assert relationships[0]["relationship_id"] == 847
    assert relationships[0]["owner_person_id"] == 110
    assert relationships[0]["is_current"] is False
    assert relationships[1]["relationship_id"] == 7797
    assert relationships[1]["owner_person_id"] == 111
    assert relationships[1]["is_current"] is True


def test_annotation_distinguishes_current_history_and_unmatched() -> None:
    document = {"owners": [_owner(110), _owner(111), _owner(200)]}
    vessels = [
        _vessel(
            vessel_id=40757,
            rank=1,
            name="Azzam",
            relationships=[
                _relationship(110, 847, current=False),
                _relationship(111, 7797, current=True),
                _relationship(999, 9000, current=True),
            ],
        ),
        _vessel(
            vessel_id=50000,
            rank=2,
            name="Second Yacht",
            relationships=[_relationship(111, 8000, current=True)],
        ),
    ]

    unmatched = annotate_top_100_owners(document, vessels)
    by_id = {owner["person_id"]: owner for owner in document["owners"]}

    assert unmatched == [999]
    assert by_id[110]["workflow"]["is_top_100_owner"] is False
    assert by_id[110]["top_100"]["historical_owner"] is True
    assert by_id[111]["workflow"]["is_top_100_owner"] is True
    assert by_id[111]["top_100"]["current_owner"] is True
    assert len(by_id[111]["top_100"]["relationships"]) == 2
    assert by_id[200]["top_100"]["relationships"] == []

    # Rebuilding annotations must not duplicate relationships.
    annotate_top_100_owners(document, vessels)
    assert len(by_id[111]["top_100"]["relationships"]) == 2


def test_workflow_backfill_transitions_and_filters() -> None:
    owner = _owner(1, enrichment_status="ok")
    workflow = ensure_owner_workflow(owner)
    assert workflow["owner_details_enriched"] is True
    assert workflow["ai_enriched"] is False
    assert workflow["updated_in_system"] is False

    workflow["is_top_100_owner"] = True
    assert owner_matches_workflow(owner, top_100_only=True)
    assert not owner_matches_workflow(owner, exclude_top_100=True)
    assert not owner_matches_workflow(owner, ai_enriched_only=True)
    assert owner_matches_workflow(owner, not_updated_only=True)

    mark_owner_details_enriched(owner)
    mark_owner_updated_in_system(owner)
    assert owner["workflow"]["owner_details_enriched"] is True
    assert owner["workflow"]["updated_in_system"] is True
    assert not owner_matches_workflow(owner, not_updated_only=True)
