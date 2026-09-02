from __future__ import annotations

from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from .auth import AuthenticationError
from .constants import (
    EXTERNAL_RELATIONSHIP_CRUD_URL,
    HTTP_TIMEOUT_SECONDS,
    VESSEL_SPECIFICATION_EDIT_URL,
)
from .parsers import ParseError, is_login_page

UBO_ROLE_ID = 1
UNDATED_ORDER_KEY = 99_999_999


class VesselOwnerOrderError(RuntimeError):
    pass


def vessel_edit_url(vessel_id: int) -> str:
    return VESSEL_SPECIFICATION_EDIT_URL.format(vessel_id=vessel_id)


def _date_part(row: Tag, name: str) -> int | None:
    raw = str(row.get(f"data-start_{name}") or "").strip()
    return int(raw) if raw.isdigit() else None


def parse_vessel_owner_order(html: str) -> list[dict[str, Any]]:
    """Read UBO rows in their persisted display order from a vessel edit page."""
    soup = BeautifulSoup(html, "lxml")
    target_fieldset: Tag | None = None
    for fieldset in soup.find_all("fieldset"):
        legend = fieldset.find("legend")
        if legend and "Ultimate Beneficial Owners" in legend.get_text(
            " ", strip=True
        ):
            target_fieldset = fieldset
            break
    if target_fieldset is None:
        raise ParseError("Ultimate Beneficial Owners fieldset was not found")

    table = target_fieldset.select_one(
        "table.jsYayContactExternalRelationshipTable"
    )
    if table is None:
        raise ParseError("Ultimate Beneficial Owners table was not found")

    relationships: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, row in enumerate(
        table.select("tbody tr.jsExternalRelationshipItem"), start=1
    ):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            raise ParseError(f"UBO row {index} has fewer than four cells")
        raw_id = str(row.get("data-id") or "").strip()
        if not raw_id.isdigit() or int(raw_id) <= 0:
            raise ParseError(f"UBO row {index} has no positive relationship ID")
        relationship_id = int(raw_id)
        if relationship_id in seen_ids:
            raise ParseError(
                f"Duplicate UBO relationship ID: {relationship_id}"
            )
        seen_ids.add(relationship_id)
        relationships.append(
            {
                "relationship_id": relationship_id,
                "entity_type_id": str(
                    row.get("data-base_entity_type_id") or ""
                ),
                "owner_name": cells[0].get_text(" ", strip=True),
                "from": cells[1].get_text(" ", strip=True),
                "to": cells[2].get_text(" ", strip=True),
                "status": cells[3].get_text(" ", strip=True),
                "start_year": _date_part(row, "year"),
                "start_month": _date_part(row, "month"),
                "start_day": _date_part(row, "day"),
            }
        )
    return relationships


def relationship_date_key(relationship: dict[str, Any]) -> int:
    year = relationship.get("start_year")
    if not isinstance(year, int):
        return UNDATED_ORDER_KEY
    month = relationship.get("start_month")
    day = relationship.get("start_day")
    return year * 10_000 + (month if isinstance(month, int) else 0) * 100 + (
        day if isinstance(day, int) else 0
    )


def build_vessel_owner_order_plan(
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mirror the site's stable oldest-first ordering operation."""
    target = sorted(relationships, key=relationship_date_key)
    before_ids = [item["relationship_id"] for item in relationships]
    target_ids = [item["relationship_id"] for item in target]
    before_positions = {
        relationship_id: index
        for index, relationship_id in enumerate(before_ids, start=1)
    }
    moves = [
        {
            "relationship_id": item["relationship_id"],
            "owner_name": item["owner_name"],
            "from_position": before_positions[item["relationship_id"]],
            "to_position": index,
        }
        for index, item in enumerate(target, start=1)
        if before_positions[item["relationship_id"]] != index
    ]
    return {
        "has_changes": before_ids != target_ids,
        "before_relationship_ids": before_ids,
        "target_relationship_ids": target_ids,
        "target_relationships": target,
        "moves": moves,
    }


def fetch_vessel_owner_order(
    session: requests.Session, vessel_id: int
) -> list[dict[str, Any]]:
    url = vessel_edit_url(vessel_id)
    response = session.get(
        url,
        headers={"Cache-Control": "no-cache"},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    html = response.text
    if is_login_page(html):
        raise AuthenticationError(
            "The authenticated session expired and returned the login page"
        )
    return parse_vessel_owner_order(html)


def submit_vessel_owner_order(
    session: requests.Session,
    *,
    vessel_id: int,
    relationship_ids: list[int],
) -> None:
    if len(relationship_ids) != len(set(relationship_ids)):
        raise VesselOwnerOrderError(
            "Refusing to submit duplicate relationship IDs"
        )
    parameters: list[tuple[str, str]] = [
        ("order[]", str(relationship_id))
        for relationship_id in relationship_ids
    ]
    parameters.extend(
        [
            ("role_id", str(UBO_ROLE_ID)),
            ("external_id", str(vessel_id)),
        ]
    )
    response = session.patch(
        EXTERNAL_RELATIONSHIP_CRUD_URL,
        params=parameters,
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    if is_login_page(response.text):
        raise AuthenticationError(
            "The authenticated session expired while saving owner order"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise VesselOwnerOrderError(
            "Owner-order update returned a non-JSON response"
        ) from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        error = (
            payload.get("error_message", "unknown error")
            if isinstance(payload, dict)
            else "unknown error"
        )
        raise VesselOwnerOrderError(f"Owner-order update failed: {error}")
