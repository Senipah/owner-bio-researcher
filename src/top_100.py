from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .constants import (
    DEFAULT_TIMEOUT_SECONDS,
    SCHEMA_VERSION,
    TOP_100_REPORT_URL,
)
from .io_utils import utc_now
from .parsers import ParseError

TOP_100_REPORT_FIELDS = (
    "vessel",
    "length",
    "beam",
    "draft",
    "gross_tonnage",
    "guests",
    "cabins",
    "crew",
    "captains_cabin",
    "built_for",
    "owner_nationality",
    "cruising_speed",
    "top_speed",
    "range",
    "fuel",
    "fresh_water",
    "interior_designer",
    "exterior_designer",
    "photo_count",
    "photo_overview",
    "photo_vs",
    "photo_tenders",
    "photo_interior",
    "photo_exterior",
    "photo_illustration",
    "photo_overhead",
    "photo_deckplan",
    "for_sale",
    "for_charter",
    "last_updated",
)

_BOOLEAN_COLUMNS = {
    "captains_cabin",
    "built_for",
    "owner_nationality",
    "interior_designer",
    "exterior_designer",
    "photo_overview",
    "photo_vs",
    "photo_tenders",
    "photo_interior",
    "photo_exterior",
    "photo_illustration",
    "photo_overhead",
    "photo_deckplan",
    "for_sale",
    "for_charter",
}


def top_100_page_url(page: int) -> str:
    parsed = urlparse(TOP_100_REPORT_URL)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["page"] = [str(page)]
    flattened = [(key, value) for key, values in query.items() for value in values]
    return urlunparse(parsed._replace(query=urlencode(flattened)))


def _indicator_value(cell: Tag) -> bool | str:
    image = cell.find("img")
    if image:
        filename = Path(urlparse(image.get("src", "")).path).name.lower()
        if filename == "tick.svg":
            return True
        if filename == "cross.svg":
            return False
    text = cell.get_text(" ", strip=True)
    return "" if text == "-" else text


def _vessel_id(url: str) -> int:
    values = parse_qs(urlparse(url).query).get("id", [])
    if not values or not values[0].isdigit():
        raise ParseError(f"Could not determine vessel ID from {url}")
    return int(values[0])


def parse_top_100_list(
    html: str,
    *,
    page_url: str,
    rank_offset: int = 0,
) -> tuple[list[dict[str, Any]], int | None, int | None]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.resultsContent.yb-fleet-vessel")
    if table is None:
        raise ParseError("Top-100 vessel results table was not found")

    vessels: list[dict[str, Any]] = []
    for row in table.find_all("tr"):
        vessel_link = row.select_one("a[href*='/vessel/view.htm?id=']")
        if vessel_link is None:
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) != len(TOP_100_REPORT_FIELDS):
            raise ParseError(
                f"Expected 30 Top-100 columns, found {len(cells)}"
            )
        specification_url = urljoin(page_url, vessel_link.get("href", ""))
        vessel_name = vessel_link.get_text(" ", strip=True)
        full_name = cells[0].get_text(" ", strip=True)
        builder_name = (
            full_name[len(vessel_name) :].strip()
            if full_name.startswith(vessel_name)
            else ""
        )
        report: dict[str, Any] = {}
        for field, cell in zip(TOP_100_REPORT_FIELDS[1:], cells[1:]):
            cell_text = cell.get_text(" ", strip=True)
            report[field] = (
                _indicator_value(cell)
                if field in _BOOLEAN_COLUMNS
                else ("" if cell_text == "-" else cell_text)
            )

        vessels.append(
            {
                "rank": rank_offset + len(vessels) + 1,
                "vessel_id": _vessel_id(specification_url),
                "vessel_name": vessel_name,
                "builder_name": builder_name,
                "specification_url": specification_url,
                "edit_url": None,
                "report": report,
                "ubo_relationships": [],
                "ownership_scan": {
                    "status": "pending",
                    "scanned_at": None,
                    "error": None,
                },
            }
        )

    next_page: int | None = None
    page_numbers: list[int] = []
    for link in soup.select("ul.jsPagination a"):
        data_page = link.get("data-page")
        if data_page and str(data_page).isdigit():
            page_numbers.append(int(data_page))
        if (
            link.get_text(" ", strip=True).lower() == "next"
            and "disabled" not in set(link.get("class", []))
            and data_page
            and str(data_page).isdigit()
        ):
            next_page = int(data_page)

    return vessels, next_page, max(page_numbers, default=None)


def parse_specification_edit_url(html: str, *, page_url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    edit_link = soup.select_one(
        "a.editButton[href*='/vessel/edit/specification_new/edit.htm']"
    )
    if edit_link is None:
        raise ParseError("Edit Details & Specification link was not found")
    return urljoin(page_url, edit_link.get("href", ""))


def parse_ubo_relationships(html: str, *, page_url: str) -> list[dict[str, Any]]:
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
    for row in table.select("tbody tr.jsExternalRelationshipItem"):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        owner_link = row.select_one(
            "a[href*='/yaycontact/vessel/owners/person/detail.htm?id=']"
        )
        owner_url = (
            urljoin(page_url, owner_link.get("href", ""))
            if owner_link
            else None
        )
        owner_person_id: int | None = None
        if owner_url:
            values = parse_qs(urlparse(owner_url).query).get("id", [])
            if values and values[0].isdigit():
                owner_person_id = int(values[0])
        relationship_id = row.get("data-id")
        relationship_id_value = (
            int(relationship_id)
            if relationship_id and str(relationship_id).isdigit()
            else None
        )
        to_value = cells[2].get_text(" ", strip=True)
        relationships.append(
            {
                "relationship_id": relationship_id_value,
                "entity_type_id": row.get("data-base_entity_type_id"),
                "owner_person_id": owner_person_id,
                "owner_name": cells[0].get_text(" ", strip=True),
                "owner_profile_url": owner_url,
                "from": cells[1].get_text(" ", strip=True),
                "to": to_value,
                "status": cells[3].get_text(" ", strip=True),
                "is_current": not bool(to_value),
            }
        )
    return relationships


def new_top_100_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": "top_100_vessels",
        "exported_at": utc_now(),
        "source": {
            "report_url": TOP_100_REPORT_URL,
            "pages_exported": 0,
            "reported_last_page": None,
            "vessel_count": 0,
            "scan_error_count": 0,
            "unmatched_owner_ids": [],
            "warnings": [],
        },
        "vessels": [],
    }


def validate_top_100_document(document: dict[str, Any]) -> None:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported Top-100 schema version")
    if document.get("dataset") != "top_100_vessels":
        raise ValueError("File is not a Top-100 vessel dataset")
    vessels = document.get("vessels")
    if not isinstance(vessels, list):
        raise ValueError("Top-100 dataset must contain a vessels array")
    vessel_ids = [item.get("vessel_id") for item in vessels]
    if any(not isinstance(item, int) for item in vessel_ids):
        raise ValueError("Every Top-100 vessel requires an integer vessel_id")
    if len(vessel_ids) != len(set(vessel_ids)):
        raise ValueError("Top-100 dataset contains duplicate vessel IDs")


class VesselOwnershipScanner:
    def __init__(self, driver, *, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def scan(self, vessel: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        self.driver.get(vessel["specification_url"])
        edit_link = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    (
                        "a.editButton"
                        "[href*='/vessel/edit/specification_new/edit.htm']"
                    ),
                )
            )
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", edit_link
        )
        try:
            edit_link.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", edit_link)

        self.wait.until(
            EC.url_contains("/vessel/edit/specification_new/edit.htm")
        )
        self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    (
                        "//fieldset[legend[contains(normalize-space(.), "
                        "'Ultimate Beneficial Owners')]]"
                    ),
                )
            )
        )
        relationships = parse_ubo_relationships(
            self.driver.page_source,
            page_url=self.driver.current_url,
        )
        return self.driver.current_url, relationships
