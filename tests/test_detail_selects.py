from __future__ import annotations

import pytest

from src.detail_selects import (
    build_detail_select_option_lookups,
    extract_detail_select_option_lookups,
    merge_detail_select_option_lookups,
    resolve_detail_select_option_id,
    strip_detail_select_options,
)


def test_extracts_complete_options_and_strips_repeated_form_data() -> None:
    details = {
        "nationality": {
            "kind": "select",
            "value": "Canadian",
            "option_id": "29",
            "option_label": "Canadian",
            "options": [
                {"value": "", "label": "Select"},
                {"value": "29", "label": "Canadian"},
                {"value": "41", "label": "Dutch"},
            ],
        }
    }

    assert extract_detail_select_option_lookups(details) == {
        "nationality": {"29": "Canadian", "41": "Dutch"}
    }

    strip_detail_select_options(details)

    assert "options" not in details["nationality"]
    assert details["nationality"]["option_id"] == "29"


def test_legacy_selected_values_are_shared_between_nationality_fields() -> None:
    document = {
        "lookups": {"social_media_types": {}},
        "owners": [
            {
                "details": {
                    "nationality": {
                        "kind": "select",
                        "value": "Canadian",
                        "option_id": "29",
                        "option_label": "Canadian",
                    },
                    "secondary_nationality": {
                        "kind": "select",
                        "value": "",
                        "option_id": "",
                        "option_label": "Select",
                    },
                }
            }
        ],
    }

    lookups = build_detail_select_option_lookups(document)

    assert lookups["secondary_nationality"] == {"29": "Canadian"}
    assert resolve_detail_select_option_id(
        lookups,
        "nationality",
        "Canadian",
    ) == "29"
    with pytest.raises(ValueError, match="not a valid system option"):
        resolve_detail_select_option_id(lookups, "nationality", "Canada")


def test_conflicting_system_option_labels_are_rejected() -> None:
    target = {"nationality": {"29": "Canadian"}}

    with pytest.raises(ValueError, match="maps to both"):
        merge_detail_select_option_lookups(
            target,
            {"nationality": {"29": "Canada"}},
        )
