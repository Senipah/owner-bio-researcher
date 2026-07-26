from __future__ import annotations

from pathlib import Path

import pytest

from src.io_utils import new_document, new_owner, set_baseline
from src.research_batch import (
    compile_research_batch,
    render_research_report,
    select_current_top_100_owners,
)


def _owner(person_id: int, name: str, rank: int, current: bool = True) -> dict:
    owner = new_owner(
        person_id=person_id,
        profile_url=f"https://example.test/person?id={person_id}",
        report={"first_name": name},
    )
    owner["details"] = {
        "display_name": {"label": "Display Name", "kind": "text", "value": name},
        "middle_names": {"label": "Middle Names", "kind": "text", "value": ""},
        "biography": {"label": "Biography", "kind": "textarea", "value": "Old"},
    }
    owner["social_media_profiles"] = []
    owner["top_100"] = {
        "current_owner": current,
        "historical_owner": not current,
        "relationships": [
            {
                "rank": rank,
                "vessel_name": f"Yacht {rank}",
                "is_current": current,
            }
        ],
    }
    owner["workflow"]["is_top_100_owner"] = current
    set_baseline(owner)
    return owner


def _dossier(person_id: int, name: str, review_status: str = "pending") -> dict:
    return {
        "owner": {
            "person_id": person_id,
            "display_name": name,
            "identity_confidence": {
                "score": 98,
                "band": "very_high",
                "reason": "Exact identity",
            },
        },
        "research_status": "complete",
        "biography": {
            "plain_text": f"{name} built an operating company and later expanded it.",
            "html": f"<p>{name} built an operating company and later expanded it.</p>\r\n",
            "confidence": {
                "score": 95,
                "band": "very_high",
                "reason": "Official sources",
            },
            "source_ids": ["S1"],
        },
        "wealth_origin": {
            "summary": "Built an operating company.",
            "confidence": {"score": 95},
        },
        "forbes_profile": {"status": "verified"},
        "proposed_details": [
            {
                "action": "fill_missing",
                "field": "middle_names",
                "value": "Example",
                "confidence": {"score": 95},
                "source_ids": ["S1"],
            }
        ],
        "proposed_socials": [
            {
                "type_id": "15",
                "type": "Personal Website",
                "url": f"https://{person_id}.example.test/",
                "confidence": {"score": 94},
                "source_ids": ["S1"],
            }
        ],
        "input_snapshot": {
            "researchable_missing_details": ["middle_names"],
        },
        "sources": [
            {
                "id": "S1",
                "url": "https://example.test/source",
                "title": "Official profile",
                "publisher": "Example",
                "tier": 1,
            }
        ],
        "candidates_requiring_review": [],
        "uncertainties": [],
        "review": (
            {"status": "pending"}
            if review_status == "pending"
            else {
                "status": review_status,
                "reviewed_by": "CEO",
                "reviewed_at": "2026-01-02T00:00:00+00:00",
            }
        ),
    }


def test_selects_unique_current_owners_by_rank() -> None:
    document = new_document()
    document["owners"] = [
        _owner(30, "Third", 3),
        _owner(10, "First", 1),
        _owner(20, "Historical", 0, current=False),
        _owner(11, "Second", 2),
    ]

    selected = select_current_top_100_owners(document, 2)

    assert [owner["person_id"] for owner in selected] == [10, 11]


def test_compiles_pending_preview_without_changing_baseline() -> None:
    document = new_document()
    owner = _owner(10, "First Owner", 1)
    document["owners"] = [owner]
    baseline_before = owner["_baseline"]
    dossier = _dossier(10, "First Owner")

    derived, report = compile_research_batch(
        document,
        {10: dossier},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    compiled = derived["owners"][0]
    assert compiled["details"]["middle_names"]["value"] == "Example"
    assert compiled["details"]["biography"]["value"].startswith("<p>")
    assert compiled["social_media_profiles"][0]["type_id"] == "15"
    assert compiled["_baseline"] == baseline_before
    assert compiled["workflow"]["ai_enriched"] is False
    assert compiled["workflow"]["updated_in_system"] is False
    assert len(report["owners"][0]["changes"]) == 3
    assert document["owners"][0]["details"]["middle_names"]["value"] == ""


def test_mark_ai_enriched_requires_approved_dossier() -> None:
    document = new_document()
    document["owners"] = [_owner(10, "First Owner", 1)]

    with pytest.raises(ValueError, match="must be approved"):
        compile_research_batch(
            document,
            {10: _dossier(10, "First Owner")},
            {10: Path("output/10.research.json")},
            source_path="output/source.json",
            limit=1,
            mark_ai_enriched=True,
        )

    approved = _dossier(10, "First Owner", review_status="approved")
    derived, _ = compile_research_batch(
        document,
        {10: approved},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=True,
    )
    assert derived["owners"][0]["workflow"]["ai_enriched"] is True


def test_rejected_dossier_keeps_owner_unchanged() -> None:
    document = new_document()
    source_owner = _owner(10, "First Owner", 1)
    document["owners"] = [source_owner]
    rejected = _dossier(10, "First Owner", review_status="rejected")

    derived, report = compile_research_batch(
        document,
        {10: rejected},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=True,
    )

    compiled = derived["owners"][0]
    assert compiled["details"] == source_owner["details"]
    assert compiled["social_media_profiles"] == []
    assert compiled["workflow"]["ai_enriched"] is False
    assert report["owners"][0]["changes"] == []


def test_renders_review_report() -> None:
    document = new_document()
    document["owners"] = [_owner(10, "First Owner", 1)]
    derived, report = compile_research_batch(
        document,
        {10: _dossier(10, "First Owner")},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
    )

    rendered = render_research_report(report)

    assert derived["owners"]
    assert "First Owner" in rendered
    assert "Missing fields added" in rendered
    assert "Official profile" in rendered
