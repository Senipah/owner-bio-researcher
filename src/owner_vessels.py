from __future__ import annotations

from copy import deepcopy
from typing import Any

import requests

from .auth import fetch_html
from .io_utils import utc_now
from .parsers import (
    parse_owner_vessel_relationships,
    parse_vessel_specification,
)


def clone_session(source: requests.Session) -> requests.Session:
    session = requests.Session()
    session.headers.update(source.headers)
    session.cookies.update(source.cookies)
    return session


def fetch_owner_vessel_relationships(
    session: requests.Session,
    owner: dict[str, Any],
) -> list[dict[str, Any]]:
    profile_url = str(owner["profile_url"])
    html = fetch_html(
        session,
        profile_url,
        expected_marker="Vessels Owned (UBO)",
    )
    return parse_owner_vessel_relationships(html, page_url=profile_url)


def fetch_vessel_specification(
    session: requests.Session,
    *,
    vessel_id: int,
    vessel_name: str,
    specification_url: str,
) -> dict[str, Any]:
    html = fetch_html(session, specification_url)
    parsed = parse_vessel_specification(html)
    return {
        "vessel_id": vessel_id,
        "vessel_name": vessel_name,
        "specification_url": specification_url,
        **parsed,
        "status": "ok" if parsed["loa_m"] is not None else "error",
        "fetched_at": utc_now(),
        "error": (
            None
            if parsed["loa_m"] is not None
            else f"LOA could not be normalized from {parsed['loa_raw']!r}"
        ),
    }


def current_vessel_references(
    owners: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    vessels: dict[int, dict[str, Any]] = {}
    for owner in owners:
        ownership = owner.get("vessel_ownership", {})
        if ownership.get("status") != "ok":
            continue
        for relationship in ownership.get("relationships", []):
            if not relationship.get("is_current"):
                continue
            vessel_id = relationship.get("vessel_id")
            if not isinstance(vessel_id, int):
                continue
            vessels.setdefault(
                vessel_id,
                {
                    "vessel_id": vessel_id,
                    "vessel_name": relationship.get("vessel_name", ""),
                    "specification_url": relationship.get(
                        "specification_url", ""
                    ),
                },
            )
    return vessels


def apply_owner_vessel_ranking(
    owner: dict[str, Any],
    vessel_specs: dict[str, dict[str, Any]],
) -> None:
    ownership = owner.get("vessel_ownership")
    if not isinstance(ownership, dict) or ownership.get("status") != "ok":
        return

    current_by_id: dict[int, dict[str, Any]] = {}
    for relationship in ownership.get("relationships", []):
        if not relationship.get("is_current"):
            continue
        vessel_id = relationship.get("vessel_id")
        if not isinstance(vessel_id, int):
            continue
        current_by_id.setdefault(vessel_id, deepcopy(relationship))

    current_vessels: list[dict[str, Any]] = []
    incomplete = False
    for vessel_id, relationship in current_by_id.items():
        spec = vessel_specs.get(str(vessel_id))
        if not isinstance(spec, dict):
            incomplete = True
            relationship["specification"] = {
                "status": "pending",
                "error": None,
            }
        else:
            relationship["specification"] = deepcopy(spec)
            if spec.get("status") != "ok" or not isinstance(
                spec.get("loa_m"), (int, float)
            ):
                incomplete = True
        current_vessels.append(relationship)

    current_vessels.sort(
        key=lambda vessel: (
            -float(vessel.get("specification", {}).get("loa_m") or -1),
            int(vessel.get("vessel_id") or 0),
        )
    )
    largest_known = next(
        (
            vessel
            for vessel in current_vessels
            if isinstance(
                vessel.get("specification", {}).get("loa_m"),
                (int, float),
            )
        ),
        None,
    )

    if not current_vessels:
        ranking_status = "no_current_vessels"
    elif incomplete:
        ranking_status = "incomplete"
    else:
        ranking_status = "ranked"

    ownership["current_vessels"] = current_vessels
    ownership["largest_known_current_vessel"] = deepcopy(largest_known)
    ownership["ranking_status"] = ranking_status
    ownership["largest_current_loa_m"] = (
        largest_known["specification"]["loa_m"] if largest_known else None
    )
    ownership["largest_current_gross_tonnage"] = (
        largest_known["specification"].get("gross_tonnage")
        if largest_known
        else None
    )


def owner_vessel_sort_key(owner: dict[str, Any]) -> tuple[Any, ...]:
    ownership = owner.get("vessel_ownership", {})
    loa = ownership.get("largest_current_loa_m")
    has_numeric_loa = isinstance(loa, (int, float))
    ranking_status = ownership.get("ranking_status")
    status_order = {
        "ranked": 0,
        "incomplete": 1,
        "no_current_vessels": 2,
    }.get(ranking_status, 3)
    return (
        0 if has_numeric_loa else 1,
        -float(loa) if has_numeric_loa else 0.0,
        status_order,
        int(owner.get("person_id") or 0),
    )


def sort_and_rank_owners(document: dict[str, Any]) -> None:
    owners = document.get("owners", [])
    owners.sort(key=owner_vessel_sort_key)
    loa_rank = 0
    previous_loa: float | None = None
    for owner in owners:
        ownership = owner.get("vessel_ownership")
        if not isinstance(ownership, dict):
            continue
        loa = ownership.get("largest_current_loa_m")
        if isinstance(loa, (int, float)):
            numeric_loa = float(loa)
            if previous_loa is None or numeric_loa != previous_loa:
                loa_rank += 1
                previous_loa = numeric_loa
            ownership["loa_rank"] = loa_rank
        else:
            ownership["loa_rank"] = None
