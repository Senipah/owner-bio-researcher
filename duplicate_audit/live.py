from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import requests

from src.auth import authenticated_context, fetch_html
from src.constants import OWNER_REPORT_URL
from src.enrichment import enrich_owner
from src.io_utils import atomic_write_json, new_document, new_owner, utc_now
from src.parsers import parse_owner_list


def _print_safe(message: str, *, file: Any = sys.stdout) -> None:
    encoding = getattr(file, "encoding", None) or "utf-8"
    rendered = message.encode(encoding, errors="replace").decode(encoding)
    print(rendered, file=file)


def export_owner_snapshot(
    session: requests.Session,
    *,
    output_path: str | Path,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Export the live owner report using GET requests only."""

    document = new_document()
    document["source"] = {
        "report_url": OWNER_REPORT_URL,
        "pages_exported": 0,
        "reported_last_page": None,
        "owner_count": 0,
        "complete": False,
        "warnings": [],
    }
    seen_ids: set[int] = set()
    seen_urls: set[str] = set()
    next_url: str | None = OWNER_REPORT_URL

    while next_url:
        if next_url in seen_urls:
            raise RuntimeError(f"Pagination loop detected at {next_url}")
        if (
            max_pages is not None
            and document["source"]["pages_exported"] >= max_pages
        ):
            document["source"]["warnings"].append(
                f"Export stopped at the requested max_pages={max_pages}"
            )
            break
        seen_urls.add(next_url)
        page_number = document["source"]["pages_exported"] + 1
        _print_safe(f"Exporting live owner report page {page_number}...")
        html = fetch_html(
            session,
            next_url,
            expected_marker="jsYayContactResultsTable",
        )
        rows, discovered_next, reported_last = parse_owner_list(
            html,
            page_url=next_url,
        )
        for row in rows:
            person_id = int(row["person_id"])
            if person_id in seen_ids:
                document["source"]["warnings"].append(
                    f"Duplicate person_id {person_id} skipped on page {page_number}"
                )
                continue
            seen_ids.add(person_id)
            document["owners"].append(
                new_owner(
                    person_id=person_id,
                    profile_url=row["profile_url"],
                    report=row["report"],
                )
            )
        document["source"]["pages_exported"] = page_number
        document["source"]["reported_last_page"] = reported_last
        document["source"]["owner_count"] = len(document["owners"])
        document["exported_at"] = utc_now()
        atomic_write_json(output_path, document)
        next_url = discovered_next

    document["source"]["complete"] = next_url is None
    document["exported_at"] = utc_now()
    atomic_write_json(output_path, document)
    return document


def export_live_owner_snapshot(
    *,
    output_path: str | Path,
    headless: bool = False,
    max_pages: int | None = None,
) -> dict[str, Any]:
    with authenticated_context(headless=headless) as context:
        return export_owner_snapshot(
            context.session,
            output_path=output_path,
            max_pages=max_pages,
        )


def enrich_owner_ids(
    session: requests.Session,
    document: dict[str, Any],
    *,
    person_ids: Iterable[int],
    output_path: str | Path,
) -> dict[str, Any]:
    """Read live details/socials for selected records and checkpoint locally."""

    owners_by_id = {int(owner["person_id"]): owner for owner in document["owners"]}
    requested_ids = list(dict.fromkeys(int(value) for value in person_ids))
    missing = sorted(set(requested_ids) - set(owners_by_id))
    if missing:
        raise ValueError(f"Candidate person IDs are absent from the snapshot: {missing}")

    eligible = [
        owners_by_id[person_id]
        for person_id in requested_ids
        if owners_by_id[person_id].get("enrichment", {}).get("status") != "ok"
    ]
    total = len(eligible)
    for index, owner in enumerate(eligible, start=1):
        person_id = int(owner["person_id"])
        report = owner.get("report", {})
        name = f"{report.get('first_name', '')} {report.get('last_name', '')}".strip()
        _print_safe(
            f"[{index}/{total}] Reading live duplicate evidence for "
            f"{person_id} {name}".rstrip()
        )
        try:
            type_lookup = enrich_owner(session, owner)
            document.setdefault("lookups", {}).setdefault(
                "social_media_types", {}
            ).update(type_lookup)
        except Exception as exc:
            owner["enrichment"] = {
                "status": "error",
                "enriched_at": None,
                "error": str(exc),
            }
            _print_safe(f"  Read failed: {exc}", file=sys.stderr)
        atomic_write_json(output_path, document)
    if not eligible:
        atomic_write_json(output_path, document)
    return document


def enrich_owner_ids_live(
    source_document: dict[str, Any],
    *,
    person_ids: Iterable[int],
    output_path: str | Path,
    headless: bool = False,
) -> dict[str, Any]:
    document = deepcopy(source_document)
    requested_ids = list(dict.fromkeys(int(value) for value in person_ids))
    owners_by_id = {int(owner["person_id"]): owner for owner in document["owners"]}
    missing = sorted(set(requested_ids) - set(owners_by_id))
    if missing:
        raise ValueError(f"Candidate person IDs are absent from the snapshot: {missing}")
    if not any(
        owners_by_id[person_id].get("enrichment", {}).get("status") != "ok"
        for person_id in requested_ids
    ):
        atomic_write_json(output_path, document)
        return document
    with authenticated_context(headless=headless) as context:
        return enrich_owner_ids(
            context.session,
            document,
            person_ids=requested_ids,
            output_path=output_path,
        )
