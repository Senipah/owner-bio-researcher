from __future__ import annotations

from pathlib import Path

import pytest

from compile_owner_research import build_parser
from src.io_utils import new_document, new_owner, set_baseline
from src.research_batch import (
    compile_research_batch,
    render_research_report,
    select_all_owners_by_loa,
    select_current_top_100_owners,
    select_largest_loa_owners,
)


def _owner(
    person_id: int,
    name: str,
    rank: int,
    current: bool = True,
    *,
    include_long_biography: bool = False,
) -> dict:
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
    if include_long_biography:
        owner["details"]["long_biography"] = {
            "label": "Long Biography",
            "kind": "textarea",
            "value": "",
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
    short_biography = (
        f"{name} is an industrial entrepreneur who built a manufacturing "
        "business from an early technical innovation. After developing the "
        "product and founding a specialist company, the owner expanded through "
        "acquisition and international growth. Later investments broadened the "
        "public profile, while the principal fortune remained rooted in the "
        "original operating business."
    )
    long_biography = (
        f"{name} entered manufacturing through technical product development "
        "and used an early innovation as the basis for a specialist operating "
        "company. The business grew through a combination of engineering, "
        "customer relationships and acquisition, eventually developing into "
        "an international supplier. That operating history, rather than later "
        "investments, remains the principal source of the owner's wealth and "
        "public standing.\n\n"
        "A subsequent phase brought investments in sport, property and other "
        "public-facing interests. Those holdings expanded the owner's profile "
        "without displacing the original industrial business at the centre of "
        "the fortune. The resulting career is best understood as a progression "
        "from technical founder to international operator and, later, a more "
        "diversified owner and investor."
    )
    return {
        "schema_version": 5,
        "record_type": "person",
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
        "biography_brief": {
            "durable_identity": f"{name} is an industrial founder.",
            "wealth_or_prominence_route": (
                "Technical product development led to an operating company."
            ),
            "turning_point": "An acquisition accelerated international growth.",
            "later_chapter": "Later activity expanded into sport and property.",
            "character_detail": "Engineering informed the founder's approach.",
            "excluded_transient_context": ["Current vessel ownership"],
            "source_ids": ["S1"],
        },
        "editorial_assessment": {
            "causal_clarity": 5,
            "human_specificity": 4,
            "durability": 5,
            "source_invisibility": 5,
            "natural_voice": 4,
            "calibration_archetypes": ["founder_operator"],
            "notes": "The profile uses a durable causal story.",
        },
        "editorial_note": None,
        "biography": {
            "plain_text": short_biography,
            "html": f"<p>{short_biography}</p>\r\n",
            "confidence": {
                "score": 95,
                "band": "very_high",
                "reason": "Official sources",
            },
            "source_ids": ["S1"],
        },
        "long_biography": {
            "plain_text": long_biography,
            "html": "".join(
                f"<p>{paragraph}</p>\r\n"
                for paragraph in long_biography.split("\n\n")
            ),
            "confidence": {
                "score": 94,
                "band": "high",
                "reason": "Official sources",
            },
            "source_ids": ["S1"],
        },
        "primary_industry": {
            "classification": "manufacturing",
            "label": "Manufacturing",
            "summary": "The principal business manufactures products.",
            "confidence": {"score": 95},
            "source_ids": ["S1"],
        },
        "wealth_origin": {
            "classification": "self_made",
            "label": "Self-made",
            "summary": "Built an operating company.",
            "confidence": {"score": 95},
            "source_ids": ["S1"],
        },
        "wealth_relationship": {
            "classification": "founder",
            "label": "Founder",
            "summary": "Founded the principal wealth-producing company.",
            "confidence": {"score": 95},
            "source_ids": ["S1"],
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


def _set_loa(
    owner: dict,
    *,
    rank: int,
    loa_m: float,
    vessel_name: str,
    ranking_status: str = "ranked",
) -> None:
    owner["vessel_ownership"] = {
        "ranking_status": ranking_status,
        "loa_rank": rank,
        "largest_current_loa_m": loa_m,
        "largest_known_current_vessel": {
            "vessel_name": vessel_name,
            "specification_url": (
                f"https://example.test/vessel/{vessel_name.casefold()}"
            ),
        },
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


def test_selects_fully_ranked_owners_by_largest_current_loa() -> None:
    small = _owner(30, "Small", 3)
    large_second = _owner(20, "Large Second", 2)
    large_first = _owner(10, "Large First", 1)
    incomplete = _owner(5, "Incomplete", 4)
    _set_loa(small, rank=2, loa_m=90.0, vessel_name="Small Yacht")
    _set_loa(
        large_second,
        rank=1,
        loa_m=120.0,
        vessel_name="Large Yacht",
    )
    _set_loa(
        large_first,
        rank=1,
        loa_m=120.0,
        vessel_name="Large Yacht",
    )
    _set_loa(
        incomplete,
        rank=1,
        loa_m=150.0,
        vessel_name="Incomplete Yacht",
        ranking_status="incomplete",
    )
    document = new_document()
    document["owners"] = [small, incomplete, large_second, large_first]

    selected = select_largest_loa_owners(document, 2)

    assert [owner["person_id"] for owner in selected] == [10, 20]


def test_selects_all_owners_with_ranked_loa_owners_first() -> None:
    small = _owner(30, "Small", 3)
    large = _owner(20, "Large", 2)
    no_current = _owner(10, "No Current Vessel", 1)
    _set_loa(small, rank=2, loa_m=90.0, vessel_name="Small Yacht")
    _set_loa(large, rank=1, loa_m=120.0, vessel_name="Large Yacht")
    no_current["vessel_ownership"] = {
        "ranking_status": "no_current_vessels",
        "loa_rank": None,
        "largest_current_loa_m": None,
        "largest_known_current_vessel": None,
    }
    document = new_document()
    document["owners"] = [no_current, small, large]

    selected = select_all_owners_by_loa(document, None)

    assert [owner["person_id"] for owner in selected] == [20, 30, 10]


def test_compiler_parser_accepts_largest_loa_selection() -> None:
    args = build_parser().parse_args(
        [
            "--input",
            "owners.json",
            "--dossier-dir",
            "dossiers",
            "--selection",
            "largest-loa",
            "--limit",
            "50",
        ]
    )

    assert args.selection == "largest-loa"
    assert args.limit == 50


def test_compiler_parser_accepts_all_by_loa_selection() -> None:
    args = build_parser().parse_args(
        [
            "--input",
            "owners.json",
            "--dossier-dir",
            "dossiers",
            "--selection",
            "all-by-loa",
            "--limit",
            "50",
        ]
    )

    assert args.selection == "all-by-loa"


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
    assert compiled["ai_research"]["primary_industry"]["label"] == "Manufacturing"
    assert compiled["ai_research"]["wealth_origin"]["label"] == "Self-made"
    assert compiled["ai_research"]["wealth_relationship"]["label"] == "Founder"
    assert compiled["ai_research"]["long_biography"]["plain_text"]
    assert len(report["owners"][0]["changes"]) == 3
    assert document["owners"][0]["details"]["middle_names"]["value"] == ""


def test_compiles_long_biography_when_owner_field_is_available() -> None:
    document = new_document()
    owner = _owner(
        10,
        "First Owner",
        1,
        include_long_biography=True,
    )
    document["owners"] = [owner]

    derived, report = compile_research_batch(
        document,
        {10: _dossier(10, "First Owner")},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
    )

    compiled = derived["owners"][0]
    assert compiled["details"]["long_biography"]["value"].startswith("<p>")
    assert compiled["_baseline"]["details"]["long_biography"]["value"] == ""
    assert any(
        change["kind"] == "long_biography"
        and change["action"] == "fill_missing"
        for change in report["owners"][0]["changes"]
    )


def test_compiles_and_renders_largest_loa_selection() -> None:
    document = new_document()
    owner = _owner(10, "Largest Owner", 1, current=False)
    _set_loa(
        owner,
        rank=1,
        loa_m=120.5,
        vessel_name="Largest Yacht",
    )
    document["owners"] = [owner]

    derived, report = compile_research_batch(
        document,
        {10: _dossier(10, "Largest Owner")},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
        selection="largest-loa",
    )
    rendered = render_research_report(report)

    assert derived["research_batch"]["selection"] == "largest-loa"
    assert report["selection"] == "largest-loa"
    assert report["owners"][0]["loa_rank"] == 1
    assert "Largest-yacht owner enrichment review" in rendered
    assert "Largest current vessel: Largest Yacht (120.5m)" in rendered


def test_compiles_and_renders_all_by_loa_unranked_owner() -> None:
    document = new_document()
    owner = _owner(10, "No Current Vessel", 1, current=False)
    owner["vessel_ownership"] = {
        "ranking_status": "no_current_vessels",
        "loa_rank": None,
        "largest_current_loa_m": None,
        "largest_known_current_vessel": None,
    }
    document["owners"] = [owner]

    derived, report = compile_research_batch(
        document,
        {10: _dossier(10, "No Current Vessel")},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
        selection="all-by-loa",
    )
    rendered = render_research_report(report)

    assert derived["research_batch"]["selection"] == "all-by-loa"
    assert "LOA-prioritised owner enrichment review" in rendered
    assert "Unranked" in rendered
    assert "No ranked current vessel" in rendered


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


def test_unresolved_dossier_is_included_unchanged_for_pending_review() -> None:
    document = new_document()
    source_owner = _owner(10, "Unknown Owner", 1)
    document["owners"] = [source_owner]
    unresolved = _dossier(10, "Unknown Owner")
    unresolved["owner"]["identity_confidence"] = {
        "score": 5,
        "band": "insufficient",
        "reason": "The source record is an unresolved placeholder.",
    }
    unresolved["record_type"] = "unresolved_placeholder"
    unresolved["research_status"] = "insufficient_evidence"
    unresolved["biography_brief"] = None
    unresolved["editorial_assessment"] = None
    unresolved["biography"] = None
    unresolved["long_biography"] = None
    unresolved["editorial_note"] = {
        "plain_text": (
            "This owner record is an unresolved placeholder rather than a "
            "verified natural person. The available public identity evidence "
            "does not support personal biography or profile changes."
        ),
        "confidence": {
            "score": 95,
            "band": "very_high",
            "reason": "The input is explicitly unresolved.",
        },
        "source_ids": ["S1"],
    }
    unresolved["proposed_details"] = []
    unresolved["proposed_socials"] = []

    derived, report = compile_research_batch(
        document,
        {10: unresolved},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
    )

    compiled = derived["owners"][0]
    assert compiled["details"] == source_owner["details"]
    assert compiled["social_media_profiles"] == []
    assert compiled["workflow"]["ai_enriched"] is False
    assert compiled["ai_research"]["research_status"] == "insufficient_evidence"
    assert compiled["ai_research"]["change_count"] == 0
    assert report["owners"][0]["identity_confidence"] == 5
    assert report["owners"][0]["changes"] == []

    with pytest.raises(ValueError, match="cannot be marked AI enriched"):
        compile_research_batch(
            document,
            {10: unresolved},
            {10: Path("output/10.research.json")},
            source_path="output/source.json",
            limit=1,
            mark_ai_enriched=True,
        )


def test_institution_dossier_renders_note_without_biography_changes() -> None:
    document = new_document()
    source_owner = _owner(10, "Example Government", 1)
    document["owners"] = [source_owner]
    institution = _dossier(10, "Example Government")
    institution["record_type"] = "institution"
    institution["research_status"] = "not_applicable"
    institution["biography_brief"] = None
    institution["editorial_assessment"] = None
    institution["biography"] = None
    institution["long_biography"] = None
    institution["editorial_note"] = {
        "plain_text": (
            "This record represents a public institution rather than a "
            "natural person. Person-specific biography, private-wealth, and "
            "social-profile proposals are therefore not applicable."
        ),
        "confidence": {
            "score": 98,
            "band": "very_high",
            "reason": "Official records establish the institution.",
        },
        "source_ids": ["S1"],
    }
    institution["proposed_details"] = []
    institution["proposed_socials"] = []

    derived, report = compile_research_batch(
        document,
        {10: institution},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
    )
    rendered = render_research_report(report)

    compiled = derived["owners"][0]
    assert compiled["details"] == source_owner["details"]
    assert compiled["ai_research"]["record_type"] == "institution"
    assert compiled["ai_research"]["biography"] is None
    assert report["owners"][0]["changes"] == []
    assert "Editorial identity note" in rendered
    assert "No biography change is proposed" in rendered


def test_renders_review_report() -> None:
    document = new_document()
    document["owners"] = [_owner(10, "First Owner", 1)]
    dossier = _dossier(10, "First Owner")
    dossier["candidates_requiring_review"] = [
        "Confirm whether this record represents an institution."
    ]
    derived, report = compile_research_batch(
        document,
        {10: dossier},
        {10: Path("output/10.research.json")},
        source_path="output/source.json",
        limit=1,
        mark_ai_enriched=False,
    )

    rendered = render_research_report(report)

    assert derived["owners"]
    assert "First Owner" in rendered
    assert "Primary industry" in rendered
    assert "Manufacturing" in rendered
    assert "Wealth origin" in rendered
    assert "Self-made" in rendered
    assert "Relationship to wealth" in rendered
    assert "Founder" in rendered
    assert "Short biography" in rendered
    assert "Longer biography" in rendered
    assert "Editorial assessment" in rendered
    assert "source invisibility: 5/5" in rendered
    assert "A subsequent phase brought investments" in rendered
    assert "Missing fields added" in rendered
    assert "Official profile" in rendered
    assert "Confirm whether this record represents an institution." in rendered
