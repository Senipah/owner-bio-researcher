from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .io_utils import load_json_unvalidated


COHORT_WORKFLOW_DEFAULTS = {
    "researched": False,
    "updated_in_system": False,
}
TERMINAL_REVIEW_STATUSES = {"complete", "approved"}


def ensure_cohort_owner_workflow(owner: dict[str, Any]) -> dict[str, bool]:
    workflow = owner.setdefault("workflow", {})
    if not isinstance(workflow, dict):
        raise ValueError("cohort owner workflow must be an object")
    for key, default in COHORT_WORKFLOW_DEFAULTS.items():
        value = workflow.setdefault(key, default)
        if type(value) is not bool:
            raise ValueError(f"cohort owner workflow.{key} must be a boolean")
    return workflow


def validate_cohort(document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    if not isinstance(document, dict):
        raise ValueError("cohort root must be an object")
    if document.get("selection") != "all-by-loa":
        raise ValueError("cohort selection must be 'all-by-loa'")
    owners = document.get("owners")
    if not isinstance(owners, list) or not owners:
        raise ValueError("cohort owners must be a non-empty list")
    if document.get("cohort_size") != len(owners):
        raise ValueError("cohort_size must match the owners array")

    owners_by_id: dict[int, dict[str, Any]] = {}
    for position, owner in enumerate(owners, start=1):
        if not isinstance(owner, dict):
            raise ValueError(f"cohort owners[{position - 1}] must be an object")
        person_id = owner.get("person_id")
        if type(person_id) is not int or person_id <= 0:
            raise ValueError(
                f"cohort owners[{position - 1}].person_id must be positive"
            )
        if person_id in owners_by_id:
            raise ValueError(f"duplicate cohort person_id {person_id}")
        if owner.get("cohort_position") != position:
            raise ValueError(
                f"cohort owner {person_id} position must be {position}"
            )
        if "workflow" in owner:
            workflow = owner["workflow"]
            if not isinstance(workflow, dict):
                raise ValueError("cohort owner workflow must be an object")
            for key in COHORT_WORKFLOW_DEFAULTS:
                if key in workflow and type(workflow[key]) is not bool:
                    raise ValueError(
                        f"cohort owner workflow.{key} must be a boolean"
                    )
        owners_by_id[person_id] = owner
    return owners_by_id


def load_researched_owner_ids(dossier_directory: Path) -> set[int]:
    paths = sorted(dossier_directory.glob("*.research.json"))
    researched: set[int] = set()
    seen: set[int] = set()
    for path in paths:
        document = load_json_unvalidated(path)
        if not isinstance(document, dict):
            raise ValueError(f"dossier root must be an object: {path}")
        owner = document.get("owner")
        person_id = owner.get("person_id") if isinstance(owner, dict) else None
        if type(person_id) is not int or person_id <= 0:
            raise ValueError(f"dossier has invalid owner.person_id: {path}")
        if person_id in seen:
            raise ValueError(f"duplicate dossier for person_id {person_id}")
        seen.add(person_id)
        review = document.get("review")
        review_status = review.get("status") if isinstance(review, dict) else None
        if review_status in TERMINAL_REVIEW_STATUSES:
            researched.add(person_id)
    return researched


def load_updated_owner_ids(paths: Iterable[Path]) -> set[int]:
    updated: set[int] = set()
    for path in paths:
        document = load_json_unvalidated(path)
        if not isinstance(document, dict):
            raise ValueError(f"owner document root must be an object: {path}")
        owners = document.get("owners")
        if not isinstance(owners, list):
            raise ValueError(f"owner document must contain owners: {path}")
        for index, owner in enumerate(owners):
            if not isinstance(owner, dict):
                raise ValueError(f"{path}: owners[{index}] must be an object")
            person_id = owner.get("person_id")
            if type(person_id) is not int or person_id <= 0:
                raise ValueError(f"{path}: owners[{index}] has invalid person_id")
            workflow = owner.get("workflow")
            if (
                isinstance(workflow, dict)
                and workflow.get("updated_in_system") is True
            ):
                updated.add(person_id)
    return updated


def prepare_cohort_status_sync(
    document: dict[str, Any],
    *,
    researched_owner_ids: set[int],
    imported_updated_owner_ids: set[int],
    mark_updated_owner_ids: set[int] | None = None,
    mark_not_updated_owner_ids: set[int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = deepcopy(document)
    owners_by_id = validate_cohort(updated)
    cohort_ids = set(owners_by_id)
    mark_updated = set(mark_updated_owner_ids or set())
    mark_not_updated = set(mark_not_updated_owner_ids or set())
    overlap = mark_updated & mark_not_updated
    if overlap:
        raise ValueError(
            "owner IDs cannot be both updated and not updated: "
            + ", ".join(map(str, sorted(overlap)))
        )
    for label, owner_ids in (
        ("researched dossiers", researched_owner_ids),
        ("imported updated owners", imported_updated_owner_ids),
        ("explicit updated owners", mark_updated),
        ("explicit not-updated owners", mark_not_updated),
    ):
        missing = owner_ids - cohort_ids
        if missing:
            raise ValueError(
                f"{label} are absent from the cohort: "
                + ", ".join(map(str, sorted(missing)))
            )

    changed_ids: list[int] = []
    for person_id, owner in owners_by_id.items():
        before = deepcopy(owner.get("workflow"))
        workflow = ensure_cohort_owner_workflow(owner)
        workflow["researched"] = person_id in researched_owner_ids
        workflow["updated_in_system"] = (
            workflow["updated_in_system"]
            or person_id in imported_updated_owner_ids
            or person_id in mark_updated
        )
        if person_id in mark_not_updated:
            workflow["updated_in_system"] = False
        if owner["workflow"] != before:
            changed_ids.append(person_id)

    researched_count = sum(
        ensure_cohort_owner_workflow(owner)["researched"]
        for owner in updated["owners"]
    )
    updated_count = sum(
        ensure_cohort_owner_workflow(owner)["updated_in_system"]
        for owner in updated["owners"]
    )
    updated_not_researched = [
        owner["person_id"]
        for owner in updated["owners"]
        if ensure_cohort_owner_workflow(owner)["updated_in_system"]
        and not ensure_cohort_owner_workflow(owner)["researched"]
    ]
    if updated_not_researched:
        raise ValueError(
            "updated owners must also be researched: "
            + ", ".join(map(str, updated_not_researched))
        )

    first_unresearched_index = next(
        (
            index
            for index, owner in enumerate(updated["owners"])
            if not ensure_cohort_owner_workflow(owner)["researched"]
        ),
        len(updated["owners"]),
    )
    researched_after_gap = [
        owner["person_id"]
        for owner in updated["owners"][first_unresearched_index + 1 :]
        if ensure_cohort_owner_workflow(owner)["researched"]
    ]
    if researched_after_gap:
        raise ValueError(
            "researched owners must form a contiguous cohort prefix; "
            "researched person IDs occur after the first gap: "
            + ", ".join(map(str, researched_after_gap))
        )

    completed_prefix = first_unresearched_index
    next_owner = (
        updated["owners"][first_unresearched_index]
        if first_unresearched_index < len(updated["owners"])
        else None
    )
    next_unresearched_owner = (
        {
            "cohort_position": next_owner["cohort_position"],
            "person_id": next_owner["person_id"],
            "display_name": next_owner.get("display_name"),
            "largest_current_vessel_name": next_owner.get(
                "largest_current_vessel_name"
            ),
            "largest_current_loa_m": next_owner.get("largest_current_loa_m"),
        }
        if next_owner is not None
        else None
    )

    previous_summary = deepcopy(updated.get("workflow_summary"))
    workflow_summary = {
        "completed_prefix": completed_prefix,
        "researched_count": researched_count,
        "updated_in_system_count": updated_count,
        "remaining_research_count": len(updated["owners"]) - researched_count,
        "next_unresearched_owner": next_unresearched_owner,
    }
    updated["workflow_summary"] = workflow_summary
    workflow_summary_changed = previous_summary != workflow_summary
    validate_cohort(updated)
    return updated, {
        "cohort_size": len(updated["owners"]),
        "researched_count": researched_count,
        "updated_in_system_count": updated_count,
        "remaining_research_count": len(updated["owners"]) - researched_count,
        "completed_prefix": completed_prefix,
        "next_unresearched_owner": next_unresearched_owner,
        "cohort_changed": bool(changed_ids or workflow_summary_changed),
        "workflow_summary_changed": workflow_summary_changed,
        "changed_owner_count": len(changed_ids),
        "changed_person_ids": changed_ids,
    }
