from __future__ import annotations

from typing import Any


WORKFLOW_DEFAULTS = {
    "is_top_100_owner": False,
    "owner_details_enriched": False,
    "ai_enriched": False,
    "updated_in_system": False,
}

TOP_100_DEFAULTS = {
    "current_owner": False,
    "historical_owner": False,
    "relationships": [],
}


def ensure_owner_workflow(owner: dict[str, Any]) -> dict[str, Any]:
    workflow = owner.setdefault("workflow", {})
    for key, default in WORKFLOW_DEFAULTS.items():
        if key not in workflow:
            if key == "owner_details_enriched":
                workflow[key] = (
                    owner.get("enrichment", {}).get("status") == "ok"
                )
            else:
                workflow[key] = default

    top_100 = owner.setdefault("top_100", {})
    for key, default in TOP_100_DEFAULTS.items():
        if key not in top_100:
            top_100[key] = [] if isinstance(default, list) else default
    return workflow


def ensure_document_workflow(document: dict[str, Any]) -> None:
    for owner in document.get("owners", []):
        ensure_owner_workflow(owner)


def mark_owner_details_enriched(owner: dict[str, Any]) -> None:
    ensure_owner_workflow(owner)["owner_details_enriched"] = True


def mark_owner_updated_in_system(owner: dict[str, Any]) -> None:
    ensure_owner_workflow(owner)["updated_in_system"] = True


def reset_top_100_annotations(document: dict[str, Any]) -> None:
    for owner in document.get("owners", []):
        workflow = ensure_owner_workflow(owner)
        workflow["is_top_100_owner"] = False
        owner["top_100"] = {
            "current_owner": False,
            "historical_owner": False,
            "relationships": [],
        }


def annotate_top_100_owners(
    document: dict[str, Any],
    vessels: list[dict[str, Any]],
) -> list[int]:
    reset_top_100_annotations(document)
    owners_by_id = {
        int(owner["person_id"]): owner for owner in document.get("owners", [])
    }
    unmatched: set[int] = set()

    for vessel in vessels:
        if vessel.get("ownership_scan", {}).get("status") != "ok":
            continue
        for relationship in vessel.get("ubo_relationships", []):
            person_id = relationship.get("owner_person_id")
            if not isinstance(person_id, int):
                continue
            owner = owners_by_id.get(person_id)
            if owner is None:
                unmatched.add(person_id)
                continue
            reference = {
                "vessel_id": vessel["vessel_id"],
                "rank": vessel["rank"],
                "vessel_name": vessel["vessel_name"],
                "relationship_id": relationship.get("relationship_id"),
                "from": relationship.get("from", ""),
                "to": relationship.get("to", ""),
                "status": relationship.get("status", ""),
                "is_current": bool(relationship.get("is_current")),
            }
            owner["top_100"]["relationships"].append(reference)

    for owner in document.get("owners", []):
        relationships = owner["top_100"]["relationships"]
        relationships.sort(
            key=lambda item: (
                item.get("rank", 10_000),
                item.get("relationship_id") or 0,
            )
        )
        current = any(item["is_current"] for item in relationships)
        historical = any(not item["is_current"] for item in relationships)
        owner["top_100"]["current_owner"] = current
        owner["top_100"]["historical_owner"] = historical
        owner["workflow"]["is_top_100_owner"] = current

    return sorted(unmatched)


def owner_matches_workflow(
    owner: dict[str, Any],
    *,
    top_100_only: bool = False,
    exclude_top_100: bool = False,
    ai_enriched_only: bool = False,
    not_updated_only: bool = False,
) -> bool:
    workflow = ensure_owner_workflow(owner)
    if top_100_only and not workflow["is_top_100_owner"]:
        return False
    if exclude_top_100 and workflow["is_top_100_owner"]:
        return False
    if ai_enriched_only and not workflow["ai_enriched"]:
        return False
    if not_updated_only and workflow["updated_in_system"]:
        return False
    return True
