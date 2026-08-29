from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "backfill_dossier_tags.py"
)
SCRIPT_DIR = SCRIPT_PATH.parent


def _load_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        specification = importlib.util.spec_from_file_location(
            "backfill_dossier_tags",
            SCRIPT_PATH,
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPT_DIR))


BACKFILL = _load_module()


def _dossier(
    text: str,
    *,
    person_id: int = 999_001,
    display_name: str = "Example Owner",
    source_support: str | None = None,
    record_type: str = "person",
) -> dict:
    source_ids = ["S1"]
    return {
        "record_type": record_type,
        "owner": {"person_id": person_id, "display_name": display_name},
        "biography": {"plain_text": text, "source_ids": source_ids},
        "long_biography": {"plain_text": text, "source_ids": source_ids},
        "biography_brief": {
            "durable_identity": text,
            "defining_work": text,
            "formative_context": "",
            "decisive_moment": "",
            "character_detail": None,
            "enduring_dimensions": [],
            "source_ids": source_ids,
        },
        "wealth_creation_industry": {
            "classification": "unknown",
            "summary": "Unknown.",
            "source_ids": source_ids,
        },
        "primary_industry": {
            "classification": "unknown",
            "summary": "Unknown.",
            "source_ids": source_ids,
        },
        "wealth_origin": {
            "classification": "unknown",
            "summary": "Unknown.",
            "source_ids": source_ids,
        },
        "wealth_relationship": {
            "classification": "unknown",
            "summary": "Unknown.",
            "source_ids": source_ids,
        },
        "sources": [
            {
                "id": "S1",
                "title": "Profile",
                "publisher": "Primary source",
                "tier": 1,
                "supports": [source_support or text],
            }
        ],
    }


def _names(document: dict) -> set[str]:
    catalogue = BACKFILL.load_tag_catalogue()
    proposals, _ = BACKFILL.assign_tags(document, catalogue)
    return {proposal["name"] for proposal in proposals}


def test_material_named_associations_exclude_lexical_collisions() -> None:
    collisions = (
        "Apple push notifications changed the messaging product.",
        "He founded a domestic steam appliance company.",
        "The president credited a valve supplier with technical progress.",
        "He made boxing gloves at a sporting-goods factory.",
        "He worked on distressed-company loans in the Ford Administration.",
    )
    names = _names(_dossier(" ".join(collisions)))
    assert {"Apple", "Steam", "Valve", "Boxing", "Ford"}.isdisjoint(names)


def test_material_long_tail_associations_are_retained() -> None:
    document = _dossier(
        "She inherited material Apple holdings. He co-founded Valve, the video "
        "game company behind Steam. The professional boxer became an eight-division "
        "boxing champion.",
        source_support=(
            "Inherited Apple stake; Valve founder and Steam game-distribution "
            "platform; professional boxing championship."
        ),
    )
    names = _names(document)
    assert {"Valve", "Video games", "Boxing"} <= names
    assert {"Apple", "Steam"}.isdisjoint(names)


def test_gambling_is_distinct_from_video_games() -> None:
    casino_owner = _dossier(
        "She built a gaming business that owns casinos and operates online betting.",
        source_support="Casino gaming and online-betting operations.",
    )
    video_game_owner = _dossier(
        "He co-founded a video-game studio and became a game publisher.",
        source_support="Video-game development and publishing.",
    )

    casino_names = _names(casino_owner)
    video_game_names = _names(video_game_owner)
    assert {"Casino operations", "Gambling", "Online gambling & betting"} <= (
        casino_names
    )
    assert "Video games" not in casino_names
    assert "Video games" in video_game_names
    assert "Gambling" not in video_game_names


def test_gambling_subtopics_retain_the_umbrella_tag() -> None:
    examples = {
        "Bookmaking": "She founded a bookmaker and expanded its retail betting shops.",
        "Casino operations": "He owns and operates a group of casino resorts.",
        "Gaming machines": "She manufactures gaming machines and slot machines.",
        "Lotteries": "He built an international lottery operator.",
        "Online gambling & betting": (
            "She founded an online gambling platform and sportsbook."
        ),
    }

    for granular_name, text in examples.items():
        names = _names(_dossier(text, source_support=text))
        assert {"Gambling", granular_name} <= names


def test_ambiguous_online_gaming_needs_gambling_classification() -> None:
    unclassified = _dossier(
        "She founded an online gaming company.",
        source_support="Online gaming company founder.",
    )
    classified = deepcopy(unclassified)
    classified["primary_industry"].update(
        {
            "classification": "gambling_casinos",
            "summary": "Her principal business is an online gaming company.",
        }
    )

    assert "Online gambling & betting" not in _names(unclassified)
    assert {"Gambling", "Online gambling & betting"} <= _names(classified)


def test_online_casino_does_not_imply_land_based_casino_operations() -> None:
    document = _dossier(
        "She founded cryptocurrency-based online casino and sports-betting brands.",
        source_support="Online casino and sports-betting company founder.",
    )

    names = _names(document)
    assert {"Gambling", "Online gambling & betting"} <= names
    assert "Casino operations" not in names


def test_gambling_classification_disambiguates_bare_gaming_language() -> None:
    document = _dossier(
        "She built her fortune through a gaming group.",
        source_support="Gaming-sector founder and owner.",
    )
    document["wealth_creation_industry"].update(
        {
            "classification": "gambling_casinos",
            "summary": "The fortune came from a gaming group.",
        }
    )

    names = _names(document)
    assert "Gambling" in names
    assert "Video games" not in names


def test_removed_generic_tags_stay_out_but_distinctive_causes_remain() -> None:
    document = _dossier(
        "She directs a family office and her charitable foundation donated to "
        "education, medical science and cancer research.",
        source_support=(
            "Family office; charitable giving to education, health and cancer "
            "research."
        ),
    )

    names = _names(document)
    assert "Cancer research / support" in names
    assert {
        "Arts & culture philanthropy",
        "Children & youth philanthropy",
        "Education philanthropy",
        "Family office",
        "Health philanthropy",
        "Science philanthropy",
    }.isdisjoint(names)


def test_government_owned_requires_a_public_owner_entity() -> None:
    government = _dossier(
        "The Government of Example is the national public institution that owns "
        "and operates the vessel on behalf of the state.",
        display_name="Example Government",
        record_type="institution",
        source_support=(
            "The Government of Example is the national public institution and "
            "registered vessel owner."
        ),
    )
    state_company = _dossier(
        "Example Energy is a state-owned energy company and public enterprise.",
        display_name="Example Energy",
        record_type="institution",
        source_support="Example Energy is a state-owned energy company.",
    )
    contractor = _dossier(
        "Example Defence is a privately owned government contractor.",
        display_name="Example Defence",
        record_type="institution",
        source_support="Privately owned government contractor.",
    )
    official = _dossier(
        "She is a government minister and chairs a state-owned energy company.",
        display_name="Example Official",
        source_support="Government minister and state-company chair.",
    )
    royal = _dossier(
        "The prince privately owns the yacht and serves as a sovereign adviser.",
        display_name="Prince Example",
        source_support="Private yacht ownership and a sovereign advisory role.",
    )

    assert "Government-owned" in _names(government)
    assert "Government-owned" in _names(state_company)
    assert "Government-owned" not in _names(contractor)
    assert "Government-owned" not in _names(official)
    assert "Government-owned" not in _names(royal)


def test_curated_family_assignments_avoid_middle_name_and_surname_collisions() -> None:
    false_reuben = _dossier(
        "Lee Reuben Anderson transformed his father's insulation business.",
        person_id=149,
        display_name="Lee Reuben Anderson",
    )
    true_reuben = _dossier(
        "Simon Reuben joined his brother in the metals business that created the "
        "family fortune.",
        person_id=1811,
        display_name="Simon Reuben",
    )
    false_yildirim = _dossier(
        "Ali Yıldırım Koç is a third-generation Koç family shareholder.",
        person_id=1189,
        display_name="Ali Yıldırım Koç",
    )
    assert "Reuben family" not in _names(false_reuben)
    assert "Reuben family" in _names(true_reuben)
    assert "Yıldırım family" not in _names(false_yildirim)


def test_royal_long_tail_implies_royalty() -> None:
    norwegian = _dossier(
        "King Harald V is Norway's constitutional monarch and head of state.",
        person_id=1617,
        display_name="King Harald V of Norway",
        source_support="King Harald V and the Norwegian monarchy.",
    )
    saudi = _dossier(
        "Prince Al-Waleed bin Talal is a Saudi prince and royal-family member.",
        person_id=281,
        display_name="Prince Al-Waleed bin Talal",
        source_support="Full formal name Prince Alwaleed Bin Talal Al Saud.",
    )
    assert {"Norwegian royal family", "Royalty"} <= _names(norwegian)
    assert {"House of Saud", "Royalty"} <= _names(saudi)


def test_sport_rules_distinguish_ownership_from_business_and_game_language() -> None:
    electronics = _dossier(
        "He owns and leads a premium consumer-electronics manufacturer."
    )
    regatta = _dossier(
        "She created a sailing event built around serious owner-led racing."
    )
    game = _dossier(
        "The game developer turned vehicle combat and car-football into Rocket League."
    )
    franchises = _dossier(
        "He owns and leads the Buffalo Bills and Buffalo Sabres professional franchises."
    )
    falcons = _dossier(
        "He bought the Atlanta Falcons and made professional sport central to "
        "his business portfolio."
    )
    assert "Professional sports ownership" not in _names(electronics)
    assert "Professional sports ownership" not in _names(regatta)
    assert "Football" not in _names(game)
    assert "Professional sports ownership" in _names(franchises)
    assert {"American football", "Professional sports ownership"} <= _names(
        falcons
    )


def test_rock_music_requires_a_performer_not_only_a_label_executive() -> None:
    executive = _dossier(
        "He founded a label built around singer-songwriters and rock artists.",
        source_support="Rock label and artist-development work.",
    )
    performer = _dossier(
        "She is a British guitarist and songwriter with a long performance career.",
        source_support="Rock and pop recording career.",
    )
    assert "Rock music" not in _names(executive)
    assert "Rock music" in _names(performer)


def test_unresolved_placeholder_is_always_tag_empty() -> None:
    document = _dossier(
        "The placeholder mentions Apple, Formula One and the House of Saud.",
        record_type="unresolved_placeholder",
    )
    assert _names(document) == set()


def test_migration_is_valid_and_deterministic() -> None:
    example_path = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / "research-owner-biography"
        / "gpt"
        / "manual-dossier.example.json"
    )
    source = json.loads(example_path.read_text(encoding="utf-8"))
    source["schema_version"] = 7
    source["owner"]["person_id"] = 1164
    source.pop("proposed_tags")
    catalogue = BACKFILL.load_tag_catalogue()

    first, _ = BACKFILL.migrate_dossier(source, catalogue)
    second, _ = BACKFILL.migrate_dossier(source, catalogue)

    assert first == second
    assert first["schema_version"] == 8
    assert isinstance(first["proposed_tags"], list)
    errors, warnings = BACKFILL.validate(first)
    assert errors == []
    assert warnings == []
    BACKFILL.resolve_dossier_tags(
        first,
        catalogue,
        person_id=first["owner"]["person_id"],
    )


def test_schema_v8_refresh_replaces_only_tags_and_is_idempotent() -> None:
    example_path = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / "research-owner-biography"
        / "gpt"
        / "manual-dossier.example.json"
    )
    source = json.loads(example_path.read_text(encoding="utf-8"))
    source["schema_version"] = 8
    source["owner"]["person_id"] = 1164
    source["proposed_tags"] = [
        {
            "tag_id": "retired_tag",
            "name": "Family office",
            "summary": "Legacy generic tag.",
            "confidence": {
                "score": 95,
                "band": "very_high",
                "reason": "Legacy proposal retained for refresh testing.",
            },
            "source_ids": ["S1"],
        }
    ]
    catalogue = BACKFILL.load_tag_catalogue()
    expected_untouched = deepcopy(source)
    expected_untouched.pop("proposed_tags")

    refreshed, _ = BACKFILL.migrate_dossier(source, catalogue)
    refreshed_untouched = deepcopy(refreshed)
    refreshed_untouched.pop("proposed_tags")
    second, _ = BACKFILL.migrate_dossier(refreshed, catalogue)

    assert refreshed_untouched == expected_untouched
    assert "Family office" not in {
        tag["name"] for tag in refreshed["proposed_tags"]
    }
    assert second == refreshed


def test_schema_v8_refresh_audit_reports_before_and_after_changes(
    tmp_path: Path,
) -> None:
    example_path = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / "research-owner-biography"
        / "gpt"
        / "manual-dossier.example.json"
    )
    source = json.loads(example_path.read_text(encoding="utf-8"))
    source["schema_version"] = 8
    source["owner"]["person_id"] = 1164
    catalogue = BACKFILL.load_tag_catalogue()
    current, _ = BACKFILL.migrate_dossier(source, catalogue)
    stale = deepcopy(current)
    stale["owner"]["person_id"] = 1165
    stale["owner"]["display_name"] = "Stale Example"
    stale["proposed_tags"] = [
        {
            "tag_id": "retired_tag",
            "name": "Family office",
            "summary": "Legacy generic tag.",
            "confidence": {
                "score": 95,
                "band": "very_high",
                "reason": "Legacy proposal retained for refresh testing.",
            },
            "source_ids": ["S1"],
        }
    ]
    (tmp_path / "1164.research.json").write_text(
        json.dumps(current),
        encoding="utf-8",
    )
    (tmp_path / "1165.research.json").write_text(
        json.dumps(stale),
        encoding="utf-8",
    )

    _, report = BACKFILL._load_and_migrate(tmp_path, catalogue)
    family_office = next(
        row for row in report["tag_counts"] if row["name"] == "Family office"
    )

    assert report["source_schema_version_counts"] == {"8": 2}
    assert report["dossier_count"] == 2
    assert report["owners_unchanged"] == 1
    assert report["owners_with_document_changes"] == 1
    assert report["owners_with_tag_set_changes"] == 1
    assert family_office == {
        "name": "Family office",
        "before_count": 1,
        "applicable_count": 0,
        "change": -1,
        "added_assignments": 0,
        "removed_assignments": 1,
        "prior_review_count": None,
        "difference": None,
    }
