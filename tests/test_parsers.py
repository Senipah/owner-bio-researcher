from __future__ import annotations

from pathlib import Path

from src.parsers import (
    parse_details_form,
    parse_owner_list,
    parse_social_form,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples"


def test_owner_report_fixture_extracts_rows_and_pagination() -> None:
    path = FIXTURES / "person-list" / "Owner Person List.html"
    owners, next_url, last_page = parse_owner_list(
        path.read_text(encoding="utf-8"),
        page_url=(
            "https://agent.superyachtnetwork.com/"
            "yaycontact/vessel/owners/person/index.htm"
        ),
    )

    assert len(owners) == 50
    assert last_page == 84
    assert next_url is not None and next_url.endswith("page=2")
    first = owners[0]
    assert first["person_id"] == 8690
    assert first["report"]["first_name"] == "Aaron"
    assert first["report"]["last_name"] == "Fidler"
    assert first["report"]["nationality"] == "Australian"
    assert first["report"]["akas"] == ""
    assert first["profile_url"].endswith("detail.htm?id=8690")


def test_details_fixture_includes_every_field_and_blanks() -> None:
    path = (
        FIXTURES
        / "person-page"
        / "details"
        / "Aaron Fidler _ Owners Edit_files"
        / "details.html"
    )
    details = parse_details_form(path.read_text(encoding="utf-8"))

    # The fixture has 32 controls representing 31 logical fields because
    # unknown_name is a two-control radio group.
    assert len(details) == 31
    assert details["display_name"]["value"] == "Aaron Fidler"
    assert details["title"]["value"] == ""
    assert details["secondary_nationality"]["value"] == ""
    assert details["secondary_nationality"]["option_id"] == ""
    assert details["nationality"]["value"] == "Australian"
    assert details["nationality"]["option_id"] == "8"
    assert details["unknown_name"]["kind"] == "radio"
    assert details["unknown_name"]["value"] == ""
    assert details["unknown_name"]["options"] == [
        {"value": "t", "label": "Yes"},
        {"value": "f", "label": "No"},
    ]
    assert details["internal_notes"]["kind"] == "rich_text_html"
    assert details["biography"]["kind"] == "rich_text_html"


def test_details_raw_textareas_preserve_known_rich_text_fields() -> None:
    details = parse_details_form(
        """
        <form name="editpersondetails">
          <textarea
            id="EditpersondetailsInternalNotes"
            name="editpersondetails[internal_notes]"
          >&lt;p&gt;Note&lt;/p&gt;</textarea>
          <textarea
            id="EditpersondetailsBiography"
            name="editpersondetails[biography]"
          >&lt;p&gt;Biography&lt;/p&gt;</textarea>
          <textarea
            id="EditpersondetailsSummary"
            name="editpersondetails[summary]"
          >Plain text</textarea>
        </form>
        """
    )

    assert details["internal_notes"]["kind"] == "rich_text_html"
    assert details["internal_notes"]["value"] == "<p>Note</p>"
    assert details["biography"]["kind"] == "rich_text_html"
    assert details["biography"]["value"] == "<p>Biography</p>"
    assert details["summary"]["kind"] == "textarea"


def test_social_fixture_extracts_profiles_and_full_type_lookup() -> None:
    path = (
        FIXTURES
        / "person-page"
        / "socials"
        / "Aaron Fidler _ Owners Edit_files"
        / "social.html"
    )
    profiles, lookup = parse_social_form(path.read_text(encoding="utf-8"))

    assert len(profiles) == 2
    assert len(lookup) == 14
    assert lookup["9"] == "Instagram"
    assert lookup["15"] == "Personal Website"
    assert profiles[0]["type"] == "Instagram"
    assert profiles[0]["url"] == "https://www.instagram.com/aaronfid/"
    assert profiles[1]["type"] == "LinkedIn"
    assert profiles[0]["profile_key"].startswith("social_")
