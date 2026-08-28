from __future__ import annotations

from pathlib import Path
from typing import Any, Collection

import requests

from .auth import fetch_html
from .constants import OWNER_DETAIL_URL
from .io_utils import load_json_unvalidated
from .parsers import parse_owner_tags
from .tags import TagCatalogue, TagResolutionError, resolve_dossier_tags


USABLE_RECORD_TYPES = {"person", "institution"}
USABLE_RESEARCH_STATUSES = {"complete", "limited"}
USABLE_REVIEW_STATUSES = {"complete", "approved"}


def fetch_owner_tags(
    session: requests.Session,
    person_id: int,
) -> list[dict[str, str]]:
    profile_url = OWNER_DETAIL_URL.format(person_id=person_id)
    html = fetch_html(
        session,
        profile_url,
        expected_marker='id="jsTagRowContainer"',
    )
    return parse_owner_tags(html)


def _skip_reason(dossier: dict[str, Any]) -> str | None:
    record_type = dossier.get("record_type")
    research_status = dossier.get("research_status")
    review = dossier.get("review")
    review_status = review.get("status") if isinstance(review, dict) else None
    if record_type not in USABLE_RECORD_TYPES:
        return f"record_type {record_type!r} is not safe for tag reconciliation"
    if research_status not in USABLE_RESEARCH_STATUSES:
        return f"research_status {research_status!r} is not usable"
    if review_status not in USABLE_REVIEW_STATUSES:
        return f"review.status {review_status!r} is not complete or approved"
    return None


def load_tag_targets(
    directory: Path,
    catalogue: TagCatalogue,
    *,
    person_ids: Collection[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load safe, canonical desired tag sets without mutating dossiers."""
    paths = sorted(directory.rglob("*.research.json"))
    if not paths:
        raise ValueError(f"No *.research.json dossiers found under {directory}")

    selected = set(person_ids or [])
    seen: dict[int, Path] = {}
    targets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    matched_ids: set[int] = set()
    for path in paths:
        dossier = load_json_unvalidated(path)
        if not isinstance(dossier, dict):
            raise ValueError(f"Dossier root must be an object: {path}")
        owner = dossier.get("owner")
        person_id = owner.get("person_id") if isinstance(owner, dict) else None
        if not isinstance(person_id, int) or person_id <= 0:
            raise ValueError(f"Dossier has invalid owner.person_id: {path}")
        if selected and person_id not in selected:
            continue
        matched_ids.add(person_id)
        if person_id in seen:
            raise ValueError(
                f"Duplicate dossier for person_id {person_id}: "
                f"{seen[person_id]} and {path}"
            )
        seen[person_id] = path
        if dossier.get("schema_version") != 8:
            raise ValueError(
                f"Dossier {path} has schema_version "
                f"{dossier.get('schema_version')!r}; run the schema-v8 tag "
                "backfill before reconciling live tags"
            )

        display_name = str(owner.get("display_name", "")).strip()
        reason = _skip_reason(dossier)
        if reason is not None:
            skipped.append(
                {
                    "person_id": person_id,
                    "display_name": display_name,
                    "dossier": str(path.resolve()),
                    "reason": reason,
                }
            )
            continue

        try:
            resolved = resolve_dossier_tags(
                dossier,
                catalogue,
                person_id=person_id,
            )
        except TagResolutionError as exc:
            raise ValueError(
                f"Dossier {path} has stale or unresolved tags; complete and "
                f"review the tag backfill before live reconciliation: {exc}"
            ) from exc
        targets.append(
            {
                "person_id": person_id,
                "display_name": display_name,
                "dossier": str(path.resolve()),
                "desired_tags": [
                    {"id": item["id"], "name": item["name"]}
                    for item in resolved
                ],
            }
        )

    missing = selected - matched_ids
    if missing:
        raise ValueError(
            "No dossier found for requested person IDs: "
            + ", ".join(str(item) for item in sorted(missing))
        )
    targets.sort(key=lambda item: item["person_id"])
    skipped.sort(key=lambda item: item["person_id"])
    return targets, skipped
