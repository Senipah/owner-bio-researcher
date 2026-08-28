from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .constants import BASE_URL, RICH_TEXT_DETAIL_FIELDS

_DETAIL_NAME_RE = re.compile(r"^editpersondetails\[([^\]]+)\]$")
_SOCIAL_TYPE_RE = re.compile(r"^social_media_type_(\d+)$")
_METRIC_LOA_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?:m|metres?|meters?)\b",
    re.IGNORECASE,
)
_IMPERIAL_LOA_RE = re.compile(
    r"(?P<feet>\d+(?:[.,]\d+)?)\s*(?:ft|feet|foot|['′])"
    r"(?:\s*(?P<inches>\d+(?:[.,]\d+)?)\s*(?:in|inches?|[\"″]))?",
    re.IGNORECASE,
)
_GROSS_TONNAGE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


class ParseError(RuntimeError):
    pass


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean_cell(cell: Tag | None) -> str:
    if cell is None:
        return ""
    value = cell.get_text(" ", strip=True)
    return "" if value == "-" else value


def _person_id_from_url(url: str) -> int:
    values = parse_qs(urlparse(url).query).get("id", [])
    if not values or not values[0].isdigit():
        raise ParseError(f"Could not determine person ID from URL: {url}")
    return int(values[0])


def parse_owner_list(
    html: str,
    *,
    page_url: str,
) -> tuple[list[dict[str, Any]], str | None, int | None]:
    soup = _soup(html)
    table = soup.select_one("table.jsYayContactResultsTable")
    if table is None:
        raise ParseError("Owner results table was not found")

    owners: list[dict[str, Any]] = []
    rows = table.find_all("tr")
    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) < 8:
            continue
        name_link = cells[1].select_one("a[href*='detail.htm?id=']")
        if name_link is None:
            continue
        profile_url = urljoin(page_url, name_link.get("href", ""))
        person_id = _person_id_from_url(profile_url)
        first_span = name_link.find("span")
        first_name = first_span.get_text(" ", strip=True) if first_span else ""
        full_name = name_link.get_text(" ", strip=True)
        last_name = (
            full_name[len(first_name) :].strip()
            if first_name and full_name.startswith(first_name)
            else full_name
        )

        image = cells[0].find("img")
        image_url = (
            urljoin(page_url, image.get("src", "")) if image and image.get("src") else ""
        )

        employer_cell = cells[4]
        employer_display = _clean_cell(employer_cell)
        employers: list[Any] = []
        raw_employers = employer_cell.get("data-employer_list")
        if raw_employers:
            try:
                parsed = json.loads(raw_employers)
                if isinstance(parsed, list):
                    employers = parsed
            except json.JSONDecodeError:
                employers = []
        if not employers and employer_display:
            employers = [{"name": employer_display}]

        owners.append(
            {
                "person_id": person_id,
                "profile_url": profile_url,
                "report": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "akas": _clean_cell(cells[2]),
                    "known_for": _clean_cell(cells[3]),
                    "employers": employers,
                    "employer_display": employer_display,
                    "nationality": _clean_cell(cells[5]),
                    "image_url": image_url,
                },
            }
        )

    next_url: str | None = None
    page_numbers: list[int] = []
    for link in soup.select("ul.jsPagination a"):
        data_page = link.get("data-page")
        if data_page and str(data_page).isdigit():
            page_numbers.append(int(data_page))
        text = link.get_text(" ", strip=True).lower()
        classes = set(link.get("class", []))
        href = link.get("href", "")
        if text == "next" and "disabled" not in classes and href and not href.endswith("#"):
            next_url = urljoin(page_url, href)

    return owners, next_url, max(page_numbers, default=None)


def _humanize(name: str) -> str:
    return name.replace("_", " ").strip().title()


def _field_label(soup: BeautifulSoup, element: Tag, key: str) -> str:
    candidates = [element.get("id"), element.get("name")]
    for candidate in candidates:
        if not candidate:
            continue
        label = soup.find("label", attrs={"for": candidate})
        if label:
            text = label.get_text(" ", strip=True).rstrip(":").strip()
            if text and text.lower() not in {"yes", "no"}:
                return text
    return _humanize(key)


def parse_details_form(html: str) -> dict[str, dict[str, Any]]:
    soup = _soup(html)
    form = soup.find("form", attrs={"name": "editpersondetails"})
    if form is None:
        raise ParseError("Owner details form was not found")

    details: dict[str, dict[str, Any]] = {}
    radio_groups: dict[str, list[Tag]] = defaultdict(list)
    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name", "")
        match = _DETAIL_NAME_RE.match(name)
        if not match:
            continue
        key = match.group(1)
        input_type = (element.get("type") or "").lower()
        if element.name == "input" and input_type == "radio":
            radio_groups[key].append(element)
            continue
        if element.name == "input" and input_type in {"hidden", "submit", "button"}:
            continue

        label = _field_label(soup, element, key)
        if element.name == "select":
            selected = element.find("option", selected=True)
            if selected is None:
                selected = element.find("option", value="")
            option_id = selected.get("value", "") if selected else ""
            option_label = selected.get_text(" ", strip=True) if selected else ""
            details[key] = {
                "label": label,
                "kind": "select",
                "value": option_label if option_id else "",
                "option_id": option_id,
                "option_label": option_label,
            }
        elif element.name == "textarea":
            element_id = element.get("id", "")
            is_rich_text = key in RICH_TEXT_DETAIL_FIELDS or bool(
                element_id and soup.find(id=f"cke_{element_id}")
            )
            details[key] = {
                "label": label,
                "kind": "rich_text_html" if is_rich_text else "textarea",
                "value": element.get_text(),
            }
        elif input_type == "checkbox":
            details[key] = {
                "label": label,
                "kind": "checkbox",
                "value": bool(element.has_attr("checked")),
            }
        else:
            details[key] = {
                "label": label,
                "kind": input_type or "text",
                "value": element.get("value", ""),
            }

    for key, elements in radio_groups.items():
        selected = next((item for item in elements if item.has_attr("checked")), None)
        options = []
        for item in elements:
            item_label = soup.find("label", attrs={"for": item.get("id")})
            options.append(
                {
                    "value": item.get("value", ""),
                    "label": (
                        item_label.get_text(" ", strip=True)
                        if item_label
                        else item.get("value", "")
                    ),
                }
            )
        details[key] = {
            "label": _field_label(soup, elements[0], key),
            "kind": "radio",
            "value": selected.get("value", "") if selected else "",
            "options": options,
        }

    return details


def social_profile_key(type_id: str, url: str, occurrence: int = 1) -> str:
    digest = hashlib.sha256(
        f"{type_id}\0{url}\0{occurrence}".encode("utf-8")
    ).hexdigest()[:16]
    return f"social_{digest}"


def parse_social_form(
    html: str,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    soup = _soup(html)
    form = soup.find("form", attrs={"name": "socialForm"})
    if form is None:
        raise ParseError("Social media form was not found")

    type_select = form.find("select", id="jsSocialMediaTypeId")
    type_lookup: dict[str, str] = {}
    if type_select:
        for option in type_select.find_all("option"):
            option_id = option.get("value", "")
            if option_id:
                type_lookup[str(option_id)] = option.get_text(" ", strip=True)

    profiles: list[dict[str, str]] = []
    occurrences: dict[tuple[str, str], int] = defaultdict(int)
    for type_input in form.find_all("input", attrs={"name": _SOCIAL_TYPE_RE}):
        match = _SOCIAL_TYPE_RE.match(type_input.get("name", ""))
        if not match:
            continue
        index = match.group(1)
        url_input = form.find("input", attrs={"name": f"social_media_url_{index}"})
        type_id = str(type_input.get("value", ""))
        url = str(url_input.get("value", "")) if url_input else ""
        pair = (type_id, url)
        occurrences[pair] += 1
        profiles.append(
            {
                "profile_key": social_profile_key(
                    type_id, url, occurrences[pair]
                ),
                "type_id": type_id,
                "type": type_lookup.get(type_id, ""),
                "url": url,
            }
        )

    return profiles, type_lookup


def parse_owner_tags(html: str) -> list[dict[str, str]]:
    """Extract live owner tags and their website association IDs."""
    soup = _soup(html)
    container = soup.select_one("#jsTagRowContainer")
    if container is None:
        raise ParseError("Owner tags container was not found")

    tags: list[dict[str, str]] = []
    seen_association_ids: set[str] = set()
    for row in container.find_all("tr", class_="jsTagRow", recursive=False):
        if row.get("id") == "jsTagRowTemplate":
            continue
        text = row.select_one(".jsTagText")
        name = text.get_text(" ", strip=True) if text is not None else ""
        if not name:
            continue
        association_id = str(row.get("data-id", "")).strip()
        if not association_id:
            raise ParseError(f"Owner tag {name!r} has no association ID")
        if association_id in seen_association_ids:
            raise ParseError(
                f"Owner tag association ID is duplicated: {association_id}"
            )
        seen_association_ids.add(association_id)
        tags.append({"association_id": association_id, "name": name})
    return tags


def _decimal_number(value: str) -> float:
    normalized = value.strip()
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    return float(normalized)


def normalize_loa_metres(raw_value: str) -> float | None:
    value = raw_value.replace("\xa0", " ").strip()
    if not value or value == "-":
        return None

    metric = _METRIC_LOA_RE.search(value)
    if metric:
        return round(_decimal_number(metric.group("value")), 3)

    imperial = _IMPERIAL_LOA_RE.search(value)
    if imperial:
        feet = _decimal_number(imperial.group("feet"))
        inches_text = imperial.group("inches")
        inches = _decimal_number(inches_text) if inches_text else 0.0
        return round((feet * 0.3048) + (inches * 0.0254), 3)

    return None


def normalize_gross_tonnage(raw_value: str) -> int | float | None:
    value = raw_value.replace("\xa0", " ").strip()
    if not value or value == "-":
        return None
    match = _GROSS_TONNAGE_RE.search(value)
    if match is None:
        return None
    number = float(match.group(0).replace(",", ""))
    return int(number) if number.is_integer() else number


def parse_owner_vessel_relationships(
    html: str,
    *,
    page_url: str,
) -> list[dict[str, Any]]:
    soup = _soup(html)
    fieldset = next(
        (
            candidate
            for candidate in soup.find_all("fieldset")
            if (
                (legend := candidate.find("legend"))
                and legend.get_text(" ", strip=True) == "Vessels Owned (UBO)"
            )
        ),
        None,
    )
    if fieldset is None:
        raise ParseError("Vessels Owned (UBO) fieldset was not found")

    table = fieldset.select_one("table.jsYayContactExternalRelationshipTable")
    if table is None:
        raise ParseError("Vessels Owned (UBO) relationship table was not found")

    relationships: list[dict[str, Any]] = []
    for row in table.select("tbody tr.jsExternalRelationshipItem"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 3:
            continue
        vessel_link = cells[0].select_one("a[href*='/vessel/view.htm?id=']")
        if vessel_link is None:
            continue
        vessel_url = urljoin(page_url, vessel_link.get("href", ""))
        vessel_id_values = parse_qs(urlparse(vessel_url).query).get("id", [])
        if not vessel_id_values or not vessel_id_values[0].isdigit():
            raise ParseError(
                f"Could not determine vessel ID from owner relationship: {vessel_url}"
            )
        relationship_id = str(row.get("data-id", ""))
        from_value = _clean_cell(cells[1])
        to_value = _clean_cell(cells[2])
        relationships.append(
            {
                "relationship_id": (
                    int(relationship_id) if relationship_id.isdigit() else None
                ),
                "vessel_id": int(vessel_id_values[0]),
                "vessel_name": vessel_link.get_text(" ", strip=True),
                "specification_url": vessel_url,
                "from": from_value,
                "to": to_value,
                "is_current": not bool(to_value),
            }
        )

    return relationships


def _specification_value(soup: BeautifulSoup, field_name: str) -> str | None:
    label = soup.find("label", attrs={"for": field_name})
    if label is None:
        return None
    value_node = label.find_next_sibling("div")
    if value_node is None:
        return None
    value = value_node.get_text(" ", strip=True)
    return "" if value == "-" else value


def parse_vessel_specification(html: str) -> dict[str, Any]:
    soup = _soup(html)
    loa_raw = _specification_value(soup, "length")
    if loa_raw is None:
        raise ParseError("Vessel LOA field was not found")
    gross_tonnage_raw = _specification_value(soup, "gross_tonnage")
    return {
        "loa_raw": loa_raw,
        "loa_m": normalize_loa_metres(loa_raw),
        "gross_tonnage_raw": gross_tonnage_raw or "",
        "gross_tonnage": normalize_gross_tonnage(gross_tonnage_raw or ""),
    }


def is_login_page(html: str) -> bool:
    soup = _soup(html)
    return soup.select_one("#LoginForm") is not None
