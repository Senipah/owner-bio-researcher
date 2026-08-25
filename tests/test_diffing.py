from __future__ import annotations

from copy import deepcopy

from src.diffing import build_owner_change_plan


def field(value: str, kind: str = "text") -> dict[str, str]:
    return {"label": "Field", "kind": kind, "value": value}


def owner_fixture() -> dict:
    details = {
        "first_name": field("Aaron"),
        "title": field("Captain"),
    }
    socials = [
        {
            "profile_key": "social_one",
            "type_id": "9",
            "type": "Instagram",
            "url": "https://instagram.com/old",
        }
    ]
    return {
        "person_id": 1,
        "details": deepcopy(details),
        "social_media_profiles": deepcopy(socials),
        "_baseline": {
            "details": deepcopy(details),
            "social_media_profiles": deepcopy(socials),
        },
    }


def test_detail_change_is_planned_when_live_matches_baseline() -> None:
    owner = owner_fixture()
    owner["details"]["first_name"]["value"] = "A."

    plan = build_owner_change_plan(
        owner,
        live_details=owner["_baseline"]["details"],
        live_socials=owner["_baseline"]["social_media_profiles"],
    )

    assert plan["has_changes"]
    assert plan["detail_changes"][0]["field"] == "first_name"
    assert not plan["conflicts"]


def test_stale_live_detail_becomes_conflict() -> None:
    owner = owner_fixture()
    owner["details"]["first_name"]["value"] = "Desired"
    live = deepcopy(owner["_baseline"]["details"])
    live["first_name"]["value"] = "Changed elsewhere"

    plan = build_owner_change_plan(
        owner,
        live_details=live,
        live_socials=owner["_baseline"]["social_media_profiles"],
    )

    assert not plan["has_changes"]
    assert plan["conflicts"][0]["field"] == "first_name"


def test_blank_changes_require_allow_clear() -> None:
    owner = owner_fixture()
    owner["details"]["title"]["value"] = ""

    safe_plan = build_owner_change_plan(owner)
    clear_plan = build_owner_change_plan(owner, allow_clear=True)

    assert safe_plan["skipped_blank_fields"] == ["title"]
    assert not safe_plan["has_changes"]
    assert clear_plan["detail_changes"][0]["to"] == ""


def test_social_add_replace_and_optional_remove() -> None:
    owner = owner_fixture()
    owner["social_media_profiles"][0]["url"] = "https://instagram.com/new"
    owner["social_media_profiles"].append(
        {
            "profile_key": "new_link",
            "type_id": "5",
            "type": "LinkedIn",
            "url": "https://linkedin.com/in/test",
        }
    )
    plan = build_owner_change_plan(owner)
    assert len(plan["social_replacements"]) == 1
    assert len(plan["social_additions"]) == 1
    assert not plan["social_removals"]

    owner["social_media_profiles"] = []
    safe_plan = build_owner_change_plan(owner)
    replace_plan = build_owner_change_plan(owner, replace_socials=True)
    assert not safe_plan["social_removals"]
    assert len(replace_plan["social_removals"]) == 1


def test_already_applied_live_values_are_no_op() -> None:
    owner = owner_fixture()
    owner["details"]["first_name"]["value"] = "Desired"
    live = deepcopy(owner["details"])

    plan = build_owner_change_plan(
        owner,
        live_details=live,
        live_socials=owner["social_media_profiles"],
    )

    assert not plan["has_changes"]
    assert not plan["conflicts"]


def test_exact_social_check_ignores_live_order() -> None:
    owner = owner_fixture()
    second = {
        "profile_key": "social_two",
        "type_id": "5",
        "type": "LinkedIn",
        "url": "https://linkedin.com/in/test",
    }
    owner["social_media_profiles"].append(deepcopy(second))
    owner["_baseline"]["social_media_profiles"].append(deepcopy(second))
    live = list(reversed(owner["social_media_profiles"]))

    plan = build_owner_change_plan(
        owner,
        live_socials=live,
        replace_socials=True,
    )

    assert not plan["conflicts"]
    assert not plan["has_changes"]


def test_detail_field_scope_ignores_other_details_and_socials() -> None:
    owner = owner_fixture()
    owner["details"]["first_name"]["value"] = "A."
    owner["details"]["title"]["value"] = "Admiral"
    owner["social_media_profiles"].append(
        {
            "profile_key": "new_link",
            "type_id": "5",
            "type": "LinkedIn",
            "url": "https://linkedin.com/in/test",
        }
    )

    plan = build_owner_change_plan(
        owner,
        detail_fields={"first_name"},
        include_socials=False,
    )

    assert [change["field"] for change in plan["detail_changes"]] == [
        "first_name"
    ]
    assert not plan["social_additions"]
    assert not plan["social_replacements"]
    assert not plan["social_removals"]


def test_rich_text_entities_compare_as_the_same_content() -> None:
    owner = owner_fixture()
    owner["details"]["biography"] = field(
        "<p>Jørn Updated</p>",
        kind="rich_text_html",
    )
    owner["_baseline"]["details"]["biography"] = field(
        "<p>J&oslash;rn Updated</p>",
        kind="rich_text_html",
    )

    plan = build_owner_change_plan(owner)

    assert not plan["has_changes"]
