from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests

from .auth import fetch_html
from .constants import OWNER_DETAILS_EDIT_URL, OWNER_SOCIAL_EDIT_URL
from .io_utils import set_baseline, utc_now
from .parsers import parse_details_form, parse_social_form
from .workflow import mark_owner_details_enriched


def fetch_owner_enrichment(
    session: requests.Session,
    person_id: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]], dict[str, str]]:
    details_url = OWNER_DETAILS_EDIT_URL.format(person_id=person_id)
    social_url = OWNER_SOCIAL_EDIT_URL.format(person_id=person_id)
    details_html = fetch_html(
        session, details_url, expected_marker='name="editpersondetails"'
    )
    social_html = fetch_html(
        session, social_url, expected_marker='name="socialForm"'
    )
    details = parse_details_form(details_html)
    socials, type_lookup = parse_social_form(social_html)
    return details, socials, type_lookup


def enrich_owner(
    session: requests.Session,
    owner: dict[str, Any],
) -> dict[str, str]:
    details, socials, type_lookup = fetch_owner_enrichment(
        session, int(owner["person_id"])
    )
    owner["details"] = details
    owner["social_media_profiles"] = socials
    set_baseline(owner)
    owner["enrichment"] = {
        "status": "ok",
        "enriched_at": utc_now(),
        "error": None,
    }
    mark_owner_details_enriched(owner)
    return type_lookup


def refreshed_owner(
    original: dict[str, Any],
    *,
    details: dict[str, dict[str, Any]],
    socials: list[dict[str, str]],
) -> dict[str, Any]:
    result = deepcopy(original)
    result["details"] = deepcopy(details)
    result["social_media_profiles"] = deepcopy(socials)
    set_baseline(result)
    result["enrichment"] = {
        "status": "ok",
        "enriched_at": utc_now(),
        "error": None,
    }
    mark_owner_details_enriched(result)
    return result
