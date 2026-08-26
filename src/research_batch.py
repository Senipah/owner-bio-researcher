from __future__ import annotations

import html
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .tags import (
    TagCatalogue,
    TagResolutionError,
    load_tag_catalogue,
    resolve_dossier_tags,
)
from .workflow import ensure_owner_workflow


RESEARCH_CLASSIFICATION_FIELDS = (
    "wealth_creation_industry",
    "primary_industry",
    "wealth_origin",
    "wealth_relationship",
)
DOSSIER_COMPARISON_FIELDS = (
    "biography",
    "long_biography",
    *RESEARCH_CLASSIFICATION_FIELDS,
)
DOSSIER_COMPARISON_LABELS = {
    "biography": "Short biography",
    "long_biography": "Longer biography",
    "wealth_creation_industry": "Wealth creation industry",
    "primary_industry": "Primary industry",
    "wealth_origin": "Wealth origin",
    "wealth_relationship": "Relationship to wealth",
}
COMPARISON_DOSSIER_SCHEMA_VERSIONS = {6, 7, 8}
BIOGRAPHY_DETAIL_FIELDS = {"biography", "long_biography"}
IMPORT_CONFIDENCE_THRESHOLD = 70
REVIEW_STATUSES = {"pending", "complete", "approved", "rejected"}
RESEARCH_SELECTIONS = {"top-100", "largest-loa", "all-by-loa"}
RESEARCH_SELECTION_DESCRIPTIONS = {
    "top-100": "current owners ordered by minimum YB Top-100 vessel rank",
    "largest-loa": (
        "fully ranked owners ordered by largest current-vessel LOA"
    ),
    "all-by-loa": (
        "all owners, with fully ranked current-vessel LOA owners first"
    ),
}


def owner_display_name(owner: dict[str, Any]) -> str:
    display = owner.get("details", {}).get("display_name", {})
    if isinstance(display, dict) and str(display.get("value", "")).strip():
        return str(display["value"]).strip()
    report = owner.get("report", {})
    return " ".join(
        str(report.get(key, "")).strip()
        for key in ("first_name", "last_name")
        if str(report.get(key, "")).strip()
    ) or f"Owner {owner.get('person_id')}"


def current_top_100_rank(owner: dict[str, Any]) -> int | None:
    ranks = [
        relationship.get("rank")
        for relationship in owner.get("top_100", {}).get("relationships", [])
        if relationship.get("is_current")
        and isinstance(relationship.get("rank"), int)
    ]
    return min(ranks) if ranks else None


def select_current_top_100_owners(
    document: dict[str, Any],
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = [
        owner
        for owner in document.get("owners", [])
        if current_top_100_rank(owner) is not None
    ]
    selected.sort(
        key=lambda owner: (
            current_top_100_rank(owner) or 10_000,
            owner["person_id"],
        )
    )
    return selected if limit is None else selected[:limit]


def largest_current_loa(owner: dict[str, Any]) -> float | None:
    ownership = owner.get("vessel_ownership")
    if not isinstance(ownership, dict):
        return None
    value = ownership.get("largest_current_loa_m")
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
    ):
        return None
    return float(value)


def current_loa_rank(owner: dict[str, Any]) -> int | None:
    ownership = owner.get("vessel_ownership")
    if (
        not isinstance(ownership, dict)
        or ownership.get("ranking_status") != "ranked"
    ):
        return None
    rank = ownership.get("loa_rank")
    if (
        not isinstance(rank, int)
        or isinstance(rank, bool)
        or rank <= 0
        or largest_current_loa(owner) is None
    ):
        return None
    return rank


def select_largest_loa_owners(
    document: dict[str, Any],
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = [
        owner
        for owner in document.get("owners", [])
        if current_loa_rank(owner) is not None
    ]
    selected.sort(
        key=lambda owner: (
            current_loa_rank(owner) or 10_000,
            -(largest_current_loa(owner) or 0.0),
            owner["person_id"],
        )
    )
    return selected if limit is None else selected[:limit]


def select_all_owners_by_loa(
    document: dict[str, Any],
    limit: int | None,
) -> list[dict[str, Any]]:
    selected = list(document.get("owners", []))

    def sort_key(owner: dict[str, Any]) -> tuple[Any, ...]:
        rank = current_loa_rank(owner)
        loa = largest_current_loa(owner)
        if rank is not None:
            return (0, rank, -(loa or 0.0), owner["person_id"])
        return (
            1 if loa is not None else 2,
            -(loa or 0.0),
            owner["person_id"],
        )

    selected.sort(key=sort_key)
    return selected if limit is None else selected[:limit]


def select_research_owners(
    document: dict[str, Any],
    selection: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    if selection == "top-100":
        return select_current_top_100_owners(document, limit)
    if selection == "largest-loa":
        return select_largest_loa_owners(document, limit)
    if selection == "all-by-loa":
        return select_all_owners_by_loa(document, limit)
    raise ValueError(
        f"Unsupported research selection {selection!r}; "
        f"expected one of {sorted(RESEARCH_SELECTIONS)}"
    )


def load_dossiers(directory: Path) -> tuple[dict[int, dict[str, Any]], dict[int, Path]]:
    dossiers: dict[int, dict[str, Any]] = {}
    paths: dict[int, Path] = {}
    for path in sorted(directory.glob("*.research.json")):
        import json

        document = json.loads(path.read_text(encoding="utf-8"))
        person_id = document.get("owner", {}).get("person_id")
        if not isinstance(person_id, int) or person_id <= 0:
            raise ValueError(f"Dossier has invalid owner.person_id: {path}")
        if person_id in dossiers:
            raise ValueError(f"Duplicate dossier for person_id {person_id}")
        dossiers[person_id] = document
        paths[person_id] = path
    return dossiers, paths


def _confidence_score(
    item: dict[str, Any],
    path: str,
    *,
    minimum: int = IMPORT_CONFIDENCE_THRESHOLD,
) -> int:
    score = item.get("confidence", {}).get("score")
    if (
        not isinstance(score, int)
        or isinstance(score, bool)
        or score < minimum
        or score > 100
    ):
        raise ValueError(
            f"{path} must have confidence between {minimum} and 100"
        )
    return score


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _source_refs(
    dossier: dict[str, Any],
    source_ids: list[str],
) -> list[dict[str, Any]]:
    sources = {
        source.get("id"): source
        for source in dossier.get("sources", [])
        if isinstance(source, dict)
    }
    return [sources[source_id] for source_id in source_ids if source_id in sources]


def _owner_vessels(owner: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "rank": relationship.get("rank"),
            "name": relationship.get("vessel_name"),
        }
        for relationship in owner.get("top_100", {}).get("relationships", [])
        if relationship.get("is_current")
    ]


def _largest_current_vessel(owner: dict[str, Any]) -> dict[str, Any] | None:
    ownership = owner.get("vessel_ownership")
    if not isinstance(ownership, dict):
        return None
    vessel = ownership.get("largest_known_current_vessel")
    if not isinstance(vessel, dict):
        return None
    return {
        "name": vessel.get("vessel_name"),
        "loa_m": largest_current_loa(owner),
        "specification_url": vessel.get("specification_url"),
    }


def _build_owner_summary(
    owner: dict[str, Any],
    dossier: dict[str, Any],
    *,
    identity_score: int,
    biography_score: int | None,
    long_biography_score: int | None,
    changes: list[dict[str, Any]],
    resolved_tags: list[dict[str, Any]],
) -> dict[str, Any]:
    unresolved_fields = sorted(
        set(
            dossier.get("input_snapshot", {}).get(
                "researchable_missing_details", []
            )
        )
        - {
            proposal.get("field")
            for proposal in dossier.get("proposed_details", [])
        }
        - BIOGRAPHY_DETAIL_FIELDS
    )
    return {
        "person_id": owner["person_id"],
        "display_name": owner_display_name(owner),
        "rank": current_top_100_rank(owner),
        "loa_rank": current_loa_rank(owner),
        "vessels": _owner_vessels(owner),
        "largest_current_vessel": _largest_current_vessel(owner),
        "record_type": dossier.get("record_type", "person"),
        "identity_confidence": identity_score,
        "biography_confidence": biography_score,
        "biography": (
            dossier.get("biography", {}).get("plain_text")
            if isinstance(dossier.get("biography"), dict)
            else None
        ),
        "long_biography_confidence": long_biography_score,
        "long_biography": (
            dossier.get("long_biography", {}).get("plain_text")
            if isinstance(dossier.get("long_biography"), dict)
            else None
        ),
        "editorial_note": dossier.get("editorial_note"),
        "editorial_assessment": dossier.get("editorial_assessment"),
        "research_status": dossier.get("research_status"),
        "review_status": dossier.get("review", {}).get("status"),
        "forbes_profile": dossier.get("forbes_profile"),
        **{
            field: dossier.get(field)
            for field in RESEARCH_CLASSIFICATION_FIELDS
        },
        "changes": changes,
        "tags": deepcopy(resolved_tags),
        "unresolved_fields": unresolved_fields,
        "candidates_requiring_review": dossier.get(
            "candidates_requiring_review", []
        ),
        "uncertainties": dossier.get("uncertainties", []),
        "sources": dossier.get("sources", []),
    }


def apply_dossier(
    owner: dict[str, Any],
    dossier: dict[str, Any],
    dossier_path: str,
    *,
    mark_ai_enriched: bool,
    generated_at: str,
    resolved_tags: list[dict[str, Any]],
) -> dict[str, Any]:
    person_id = owner["person_id"]
    if dossier.get("owner", {}).get("person_id") != person_id:
        raise ValueError(f"Dossier owner mismatch for person_id {person_id}")
    record_type = dossier.get("record_type", "person")
    research_status = dossier.get("research_status")
    unusable_research = (
        record_type == "unresolved_placeholder"
        or research_status
        in {
            "identity_conflict",
            "insufficient_evidence",
            "not_applicable",
        }
    )
    identity_score = _confidence_score(
        {"confidence": dossier.get("owner", {}).get("identity_confidence", {})},
        f"owner {person_id} identity",
        minimum=0 if unusable_research else 85,
    )

    review_status = dossier.get("review", {}).get("status")
    if review_status not in REVIEW_STATUSES:
        raise ValueError(f"Owner {person_id} has invalid review status")
    if review_status in {"approved", "rejected"} and any(
        not isinstance(dossier.get("review", {}).get(key), str)
        or not dossier["review"][key].strip()
        for key in ("reviewed_by", "reviewed_at")
    ):
        raise ValueError(
            f"Owner {person_id} final review requires reviewed_by and reviewed_at"
        )
    if (
        mark_ai_enriched
        and not unusable_research
        and review_status == "pending"
    ):
        raise ValueError(
            f"Owner {person_id} review status must be complete or approved "
            "before marking AI enriched"
        )

    changes: list[dict[str, Any]] = []
    compiled_tags = deepcopy(resolved_tags)
    for tag in compiled_tags:
        tag["sources"] = _source_refs(dossier, tag.get("source_ids", []))
    biography = dossier.get("biography")
    long_biography = dossier.get("long_biography")
    biography_score: int | None = None
    long_biography_score: int | None = None
    if record_type in {"person", "institution"}:
        if not isinstance(biography, dict):
            raise ValueError(f"Owner {person_id} has no dossier biography")
        biography_score = _confidence_score(
            biography,
            f"owner {person_id} biography",
        )
        if not isinstance(long_biography, dict):
            raise ValueError(f"Owner {person_id} has no dossier long_biography")
        long_biography_score = _confidence_score(
            long_biography,
            f"owner {person_id} long biography",
        )
    elif biography is not None or long_biography is not None:
        raise ValueError(
            f"Owner {person_id} unresolved dossier must not contain biographies"
        )
    if review_status == "rejected" or unusable_research:
        workflow = ensure_owner_workflow(owner)
        workflow["ai_enriched"] = False
        owner["ai_research"] = {
            "dossier": dossier_path.replace("\\", "/"),
            "record_type": record_type,
            "research_status": dossier.get("research_status"),
            "review_status": review_status,
            "compiled_at": generated_at,
            "change_count": 0,
            "tags": deepcopy(compiled_tags),
            "biography_brief": deepcopy(dossier.get("biography_brief")),
            "editorial_assessment": deepcopy(
                dossier.get("editorial_assessment")
            ),
            "biography": deepcopy(biography),
            "long_biography": deepcopy(long_biography),
            "editorial_note": deepcopy(dossier.get("editorial_note")),
            **{
                field: deepcopy(dossier.get(field))
                for field in RESEARCH_CLASSIFICATION_FIELDS
            },
        }
        return _build_owner_summary(
            owner,
            dossier,
            identity_score=identity_score,
            biography_score=biography_score,
            long_biography_score=long_biography_score,
            changes=[],
            resolved_tags=compiled_tags,
        )

    details = owner.get("details")
    if not isinstance(details, dict):
        raise ValueError(f"Owner {person_id} has no details object")

    biography_field = details.get("biography")
    if not isinstance(biography_field, dict):
        raise ValueError(f"Owner {person_id} input has no biography field")
    before_biography = biography_field.get("value")
    after_biography = biography.get("html")
    if not isinstance(after_biography, str) or not after_biography.strip():
        raise ValueError(f"Owner {person_id} biography HTML is empty")
    biography_field["value"] = after_biography
    if before_biography != after_biography:
        changes.append(
            {
                "kind": "biography",
                "action": (
                    "fill_missing" if _blank(before_biography)
                    else "correct_existing"
                ),
                "field": "biography",
                "label": "Biography",
                "before": before_biography,
                "after": biography.get("plain_text"),
                "confidence": biography_score,
                "source_ids": biography.get("source_ids", []),
            }
        )

    before_long_biography = None
    after_long_biography = long_biography.get("html")
    if (
        not isinstance(after_long_biography, str)
        or not after_long_biography.strip()
    ):
        raise ValueError(f"Owner {person_id} long biography HTML is empty")
    long_biography_field = details.get("long_biography")
    if long_biography_field is not None:
        if not isinstance(long_biography_field, dict):
            raise ValueError(
                f"Owner {person_id} long_biography field is not editable"
            )
        before_long_biography = long_biography_field.get("value")
        long_biography_field["value"] = after_long_biography
        if before_long_biography != after_long_biography:
            changes.append(
                {
                    "kind": "long_biography",
                    "action": (
                        "fill_missing" if _blank(before_long_biography)
                        else "correct_existing"
                    ),
                    "field": "long_biography",
                    "label": "Long Biography",
                    "before": before_long_biography,
                    "after": long_biography.get("plain_text"),
                    "confidence": long_biography_score,
                    "source_ids": long_biography.get("source_ids", []),
                }
            )

    biography_values = {
        "biography": (before_biography, after_biography),
        "long_biography": (
            before_long_biography,
            after_long_biography,
        ),
    }
    for index, proposal in enumerate(dossier.get("proposed_details", [])):
        field = proposal.get("field")
        if not isinstance(field, str) or field not in details:
            raise ValueError(
                f"Owner {person_id} proposal {index} has unknown field {field!r}"
            )
        score = _confidence_score(
            proposal,
            f"owner {person_id} detail proposal {field}",
        )
        if field in BIOGRAPHY_DETAIL_FIELDS:
            before_value, after_value = biography_values[field]
            if proposal.get("value") != after_value:
                raise ValueError(
                    f"Owner {person_id} {field} proposal differs from "
                    f"{field}.html"
                )
            if (
                proposal.get("action") == "fill_missing"
                and not _blank(before_value)
            ):
                raise ValueError(
                    f"Owner {person_id} {field} is no longer blank"
                )
            if (
                proposal.get("action") == "correct_existing"
                and proposal.get("existing_value") != before_value
            ):
                raise ValueError(
                    f"Owner {person_id} {field} no longer matches "
                    "the correction baseline"
                )
            continue
        detail = details[field]
        if not isinstance(detail, dict):
            raise ValueError(f"Owner {person_id} field {field} is not editable")
        before = detail.get("value")
        if proposal.get("action") == "fill_missing" and not _blank(before):
            raise ValueError(
                f"Owner {person_id} field {field} is no longer blank"
            )
        if (
            proposal.get("action") == "correct_existing"
            and proposal.get("existing_value") != before
        ):
            raise ValueError(
                f"Owner {person_id} field {field} no longer matches "
                "the correction baseline"
            )
        after = proposal.get("value")
        detail["value"] = after
        changes.append(
            {
                "kind": "detail",
                "action": proposal.get("action"),
                "field": field,
                "label": detail.get("label", field),
                "before": before,
                "after": after,
                "confidence": score,
                "source_ids": proposal.get("source_ids", []),
            }
        )

    profiles = owner.get("social_media_profiles")
    if not isinstance(profiles, list):
        raise ValueError(f"Owner {person_id} has no social profile list")
    existing_types = {
        str(profile.get("type_id"))
        for profile in profiles
        if isinstance(profile, dict)
    }
    for index, proposal in enumerate(dossier.get("proposed_socials", [])):
        type_id = str(proposal.get("type_id", ""))
        if type_id in existing_types:
            raise ValueError(
                f"Owner {person_id} already has social type_id {type_id}"
            )
        score = _confidence_score(
            proposal,
            f"owner {person_id} social proposal {index}",
        )
        profile = {
            "type_id": type_id,
            "type": proposal.get("type"),
            "url": proposal.get("url"),
        }
        profiles.append(profile)
        existing_types.add(type_id)
        changes.append(
            {
                "kind": "social",
                "action": "fill_missing",
                "field": proposal.get("type"),
                "label": proposal.get("type"),
                "before": None,
                "after": proposal.get("url"),
                "confidence": score,
                "source_ids": proposal.get("source_ids", []),
            }
        )

    workflow = ensure_owner_workflow(owner)
    workflow["ai_enriched"] = bool(mark_ai_enriched)
    if changes:
        workflow["updated_in_system"] = False
    owner["ai_research"] = {
        "dossier": dossier_path.replace("\\", "/"),
        "record_type": record_type,
        "research_status": dossier.get("research_status"),
        "review_status": review_status,
        "compiled_at": generated_at,
        "change_count": len(changes),
        "tags": deepcopy(compiled_tags),
        "biography_brief": deepcopy(dossier.get("biography_brief")),
        "editorial_assessment": deepcopy(dossier.get("editorial_assessment")),
        "biography": deepcopy(biography),
        "long_biography": deepcopy(long_biography),
        "editorial_note": deepcopy(dossier.get("editorial_note")),
        **{
            field: deepcopy(dossier.get(field))
            for field in RESEARCH_CLASSIFICATION_FIELDS
        },
    }
    for change in changes:
        change["sources"] = _source_refs(dossier, change["source_ids"])

    return _build_owner_summary(
        owner,
        dossier,
        identity_score=identity_score,
        biography_score=biography_score,
        long_biography_score=long_biography_score,
        changes=changes,
        resolved_tags=compiled_tags,
    )


def compile_research_batch(
    source_document: dict[str, Any],
    dossiers: dict[int, dict[str, Any]],
    dossier_paths: dict[int, Path],
    *,
    source_path: str,
    limit: int | None,
    mark_ai_enriched: bool,
    selection: str = "top-100",
    generated_at: str | None = None,
    tag_catalogue: TagCatalogue | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    timestamp = generated_at or datetime.now(UTC).isoformat()
    selected = select_research_owners(source_document, selection, limit)
    if not selected:
        raise ValueError(
            f"No owners matched research selection {selection!r}"
        )
    missing = [
        owner["person_id"]
        for owner in selected
        if owner["person_id"] not in dossiers
    ]
    if missing:
        raise ValueError(f"Missing dossiers for person IDs: {missing}")

    catalogue = tag_catalogue or load_tag_catalogue()
    resolved_tags_by_owner: dict[int, list[dict[str, Any]]] = {}
    resolution_issues: list[str] = []
    for source_owner in selected:
        person_id = source_owner["person_id"]
        try:
            resolved_tags_by_owner[person_id] = resolve_dossier_tags(
                dossiers[person_id],
                catalogue,
                person_id=person_id,
            )
        except TagResolutionError as exc:
            resolution_issues.append(str(exc))
    if resolution_issues:
        detail = "\n".join(resolution_issues)
        raise TagResolutionError(f"Tag resolution failed:\n{detail}")

    derived = deepcopy(source_document)
    compiled_owners: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for source_owner in selected:
        person_id = source_owner["person_id"]
        owner = deepcopy(source_owner)
        summary = apply_dossier(
            owner,
            dossiers[person_id],
            str(dossier_paths[person_id]),
            mark_ai_enriched=mark_ai_enriched,
            generated_at=timestamp,
            resolved_tags=resolved_tags_by_owner[person_id],
        )
        compiled_owners.append(owner)
        summaries.append(summary)

    original_count = len(source_document.get("owners", []))
    derived["owners"] = compiled_owners
    source = derived.setdefault("source", {})
    source["original_owner_count"] = original_count
    source["owner_count"] = len(compiled_owners)
    source["derived_from"] = source_path.replace("\\", "/")
    derived["research_batch"] = {
        "schema_version": 1,
        "generated_at": timestamp,
        "selection": selection,
        "selection_description": RESEARCH_SELECTION_DESCRIPTIONS[selection],
        "limit": limit,
        "review_state": (
            "complete" if mark_ai_enriched else "not_marked_ai_enriched"
        ),
        "owner_count": len(compiled_owners),
        "tag_catalogue": {
            "schema_version": catalogue.document.get("schema_version"),
            "source_path": catalogue.source_reference,
        },
    }
    report = {
        "generated_at": timestamp,
        "source_path": source_path.replace("\\", "/"),
        "mark_ai_enriched": mark_ai_enriched,
        "selection": selection,
        "selection_description": RESEARCH_SELECTION_DESCRIPTIONS[selection],
        "tag_catalogue": {
            "schema_version": catalogue.document.get("schema_version"),
            "source_path": catalogue.source_reference,
        },
        "owners": summaries,
    }
    return derived, report


def attach_biography_comparisons(
    report: dict[str, Any],
    earlier_dossiers: dict[int, dict[str, Any]],
    *,
    source_directory: str,
) -> int:
    """Attach material dossier-field comparisons to a compiled report.

    The historical function and report key retain their biography-oriented
    names for compatibility. New payloads also compare the four wealth
    classification objects.
    """
    owners = report.get("owners")
    if not isinstance(owners, list):
        raise ValueError("Research report has no owner summaries")

    changed_owner_count_by_field = {
        field: 0 for field in DOSSIER_COMPARISON_FIELDS
    }
    wealth_origin_transitions: dict[str, int] = {}
    comparison_count = 0
    for cohort_position, owner in enumerate(owners, start=1):
        if not isinstance(owner, dict):
            raise ValueError("Research report contains an invalid owner summary")
        person_id = owner.get("person_id")
        if not isinstance(person_id, int):
            raise ValueError("Research report owner summary has no person_id")
        earlier = earlier_dossiers.get(person_id)
        if earlier is None:
            raise ValueError(
                "Comparison dossier is missing for person_id "
                f"{person_id}"
            )
        if (
            earlier.get("schema_version")
            not in COMPARISON_DOSSIER_SCHEMA_VERSIONS
        ):
            raise ValueError(
                "Comparison dossier schema_version is not supported for "
                f"person_id {person_id}"
            )
        if earlier.get("owner", {}).get("person_id") != person_id:
            raise ValueError(
                "Comparison dossier owner mismatch for person_id "
                f"{person_id}"
            )
        if earlier.get("record_type") != owner.get("record_type"):
            raise ValueError(
                "Comparison dossier record_type mismatch for person_id "
                f"{person_id}"
            )
        owner.pop("biography_comparison", None)
        owner.pop("comparison_cohort_position", None)
        changed_fields: dict[str, dict[str, Any]] = {}

        if owner.get("record_type") == "person":
            for field in ("biography", "long_biography"):
                earlier_biography = earlier.get(field)
                if not isinstance(earlier_biography, dict):
                    raise ValueError(
                        "Comparison person dossier has no "
                        f"{field} for person_id {person_id}"
                    )
                before = earlier_biography.get("plain_text")
                after = owner.get(field)
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (before, after)
                ):
                    raise ValueError(
                        "Biography comparison text is missing for person_id "
                        f"{person_id}"
                    )
                normalised_before = _normalise_biography_text(before)
                normalised_after = _normalise_biography_text(after)
                if normalised_before != normalised_after:
                    changed_fields[field] = {
                        "before": normalised_before,
                        "after": normalised_after,
                    }

        for field in RESEARCH_CLASSIFICATION_FIELDS:
            earlier_value = earlier.get(field)
            after_value = owner.get(field)
            # Schema-v6 comparisons historically covered biographies only and
            # may not contain wealth_creation_industry.
            if earlier_value is None and earlier.get("schema_version") == 6:
                continue
            if not isinstance(earlier_value, dict) or not isinstance(
                after_value,
                dict,
            ):
                raise ValueError(
                    f"Comparison field {field} is missing for person_id "
                    f"{person_id}"
                )
            before = _wealth_comparison_value(earlier_value)
            after = _wealth_comparison_value(after_value)
            if before != after:
                changed_fields[field] = {
                    "before": before,
                    "after": after,
                }
                if (
                    field == "wealth_origin"
                    and before.get("classification")
                    != after.get("classification")
                ):
                    transition = (
                        f"{before.get('classification')} "
                        f"\N{RIGHTWARDS ARROW} "
                        f"{after.get('classification')}"
                    )
                    wealth_origin_transitions[transition] = (
                        wealth_origin_transitions.get(transition, 0) + 1
                    )

        if not changed_fields:
            continue

        owner["comparison_cohort_position"] = cohort_position
        owner["biography_comparison"] = {
            "changed_fields": [
                field
                for field in DOSSIER_COMPARISON_FIELDS
                if field in changed_fields
            ],
            "fields": changed_fields,
            # Retain the legacy biography-only projection for callers that
            # consume the before/after keys directly.
            "before": {
                field: value["before"]
                for field, value in changed_fields.items()
                if field in BIOGRAPHY_DETAIL_FIELDS
            },
            "after": {
                field: value["after"]
                for field, value in changed_fields.items()
                if field in BIOGRAPHY_DETAIL_FIELDS
            },
        }
        for field in changed_fields:
            changed_owner_count_by_field[field] += 1
        comparison_count += 1

    report["biography_comparison"] = {
        "source_directory": source_directory.replace("\\", "/"),
        "owner_count": comparison_count,
        "owners_reviewed": len(owners),
        "owners_with_changes": comparison_count,
        "unchanged_owners": len(owners) - comparison_count,
        "changed_owner_count_by_field": changed_owner_count_by_field,
        "wealth_origin_transitions": dict(
            sorted(wealth_origin_transitions.items())
        ),
    }
    return comparison_count


def _normalise_biography_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _wealth_comparison_value(value: dict[str, Any]) -> dict[str, Any]:
    confidence = value.get("confidence")
    if not isinstance(confidence, dict):
        confidence = {}
    return {
        "classification": value.get("classification"),
        "label": value.get("label"),
        "summary": value.get("summary"),
        "confidence": {
            "score": confidence.get("score"),
            "reason": confidence.get("reason"),
        },
    }


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _plain_paragraphs(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return '<p class="muted">No biography supplied.</p>'
    return "".join(
        f"<p>{_e(paragraph)}</p>"
        for paragraph in value.split("\n\n")
    )


def _confidence_badge(score: Any) -> str:
    numeric = int(score) if isinstance(score, int) else 0
    level = "high" if numeric >= 95 else "medium" if numeric >= 70 else "low"
    return f'<span class="confidence {level}">{numeric}%</span>'


def _source_links(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return '<span class="muted">No source link recorded</span>'
    return ", ".join(
        f'<a href="{_e(source.get("url"))}" target="_blank" '
        f'rel="noopener noreferrer">{_e(source.get("publisher"))}: '
        f'{_e(source.get("title"))}</a>'
        for source in sources
    )


def _comparison_panel_content(field: str, value: Any) -> str:
    if field == "biography":
        return f"<blockquote>{_e(value)}</blockquote>"
    if field == "long_biography":
        return (
            '<div class="long-biography">'
            f"{_plain_paragraphs(value)}"
            "</div>"
        )
    if not isinstance(value, dict):
        return '<p class="muted">No comparison value supplied.</p>'
    confidence = value.get("confidence")
    if not isinstance(confidence, dict):
        confidence = {}
    return f"""
      <dl class="comparison-details">
        <dt>Classification</dt>
        <dd><code>{_e(value.get("classification"))}</code></dd>
        <dt>Label</dt><dd>{_e(value.get("label"))}</dd>
        <dt>Summary</dt><dd>{_e(value.get("summary"))}</dd>
        <dt>Confidence</dt><dd>{_e(confidence.get("score"))}%</dd>
        <dt>Confidence reason</dt>
        <dd>{_e(confidence.get("reason"))}</dd>
      </dl>
    """


def _comparison_pair(
    field: str,
    values: dict[str, Any],
    *,
    confidence_score: Any = None,
) -> str:
    confidence = (
        f" {_confidence_badge(confidence_score)}"
        if confidence_score is not None
        else ""
    )
    return f"""
      <h3>{_e(DOSSIER_COMPARISON_LABELS[field])}
      &mdash; before and after{confidence}</h3>
      <div class="comparison-grid" data-comparison-field="{_e(field)}">
        <section class="comparison-panel before">
          <h4>Before</h4>
          {_comparison_panel_content(field, values.get("before"))}
        </section>
        <section class="comparison-panel after">
          <h4>After</h4>
          {_comparison_panel_content(field, values.get("after"))}
        </section>
      </div>
    """


def render_research_report(report: dict[str, Any]) -> str:
    owners = report.get("owners", [])
    selection = report.get("selection", "top-100")
    selection_description = report.get(
        "selection_description",
        RESEARCH_SELECTION_DESCRIPTIONS["top-100"],
    )
    if selection == "largest-loa":
        report_title = "Largest-yacht owner enrichment review"
    elif selection == "all-by-loa":
        report_title = "LOA-prioritised owner enrichment review"
    else:
        report_title = "Top-100 owner enrichment review"
    field_additions = sum(
        1
        for owner in owners
        for change in owner.get("changes", [])
        if change.get("kind") == "detail"
        and change.get("action") == "fill_missing"
    )
    link_additions = sum(
        1
        for owner in owners
        for change in owner.get("changes", [])
        if change.get("kind") == "social"
    )
    resolved_tag_count = sum(
        len(owner.get("tags", [])) for owner in owners
    )
    comparison = report.get("biography_comparison")
    comparison_count = (
        int(comparison.get("owner_count", 0))
        if isinstance(comparison, dict)
        else 0
    )
    comparison_source = (
        comparison.get("source_directory")
        if isinstance(comparison, dict)
        else None
    )
    comparison_reviewed = (
        int(comparison.get("owners_reviewed", len(owners)))
        if isinstance(comparison, dict)
        else 0
    )
    comparison_unchanged = (
        int(comparison.get("unchanged_owners", len(owners) - comparison_count))
        if isinstance(comparison, dict)
        else 0
    )
    changed_owner_count_by_field = (
        comparison.get("changed_owner_count_by_field", {})
        if isinstance(comparison, dict)
        else {}
    )
    if not isinstance(changed_owner_count_by_field, dict):
        changed_owner_count_by_field = {}
    wealth_origin_transitions = (
        comparison.get("wealth_origin_transitions", {})
        if isinstance(comparison, dict)
        else {}
    )
    if not isinstance(wealth_origin_transitions, dict):
        wealth_origin_transitions = {}
    comparison_summary = ""
    if isinstance(comparison, dict):
        field_items = "".join(
            "<li>"
            f"{_e(DOSSIER_COMPARISON_LABELS[field])}: "
            f"<strong>{_e(changed_owner_count_by_field.get(field, 0))}</strong>"
            "</li>"
            for field in DOSSIER_COMPARISON_FIELDS
        )
        transition_items = (
            "".join(
                f"<li><code>{_e(transition)}</code>: "
                f"<strong>{_e(count)}</strong></li>"
                for transition, count in wealth_origin_transitions.items()
            )
            or '<li class="muted">No wealth-origin classification transitions.</li>'
        )
        comparison_summary = f"""
          <section class="comparison-summary">
            <h2>Comparison summary</h2>
            <p>Compared <strong>{comparison_reviewed}</strong> owners against
            <code>{_e(comparison_source)}</code>:
            <strong>{comparison_count}</strong> changed and
            <strong>{comparison_unchanged}</strong> unchanged.</p>
            <div class="comparison-summary-grid">
              <div><h3>Changed owners by field</h3><ul>{field_items}</ul></div>
              <div><h3>Wealth-origin transitions</h3>
              <ul>{transition_items}</ul></div>
            </div>
          </section>
        """
    cards: list[str] = []
    for owner in owners:
        display_rank = owner.get("rank")
        rank_label = f"#{display_rank}"
        if selection in {"largest-loa", "all-by-loa"}:
            display_rank = owner.get("loa_rank")
            rank_label = (
                f"#{display_rank}"
                if isinstance(display_rank, int)
                else "Unranked"
            )
            largest = owner.get("largest_current_vessel") or {}
            loa = largest.get("loa_m")
            loa_text = (
                f"{float(loa):g}m"
                if isinstance(loa, (int, float))
                else "LOA unavailable"
            )
            vessels = (
                (
                    f"Largest current vessel: {_e(largest.get('name'))} "
                    f"({_e(loa_text)})"
                )
                if largest
                else "No ranked current vessel"
            )
        else:
            vessels = ", ".join(
                f'#{_e(vessel.get("rank"))} {_e(vessel.get("name"))}'
                for vessel in owner.get("vessels", [])
            )
        detail_rows = []
        improvement_rows = []
        link_rows = []
        for change in owner.get("changes", []):
            if change.get("kind") in BIOGRAPHY_DETAIL_FIELDS:
                continue
            if change.get("action") == "correct_existing":
                improvement_rows.append(
                    "<tr>"
                    f"<td>{_e(change.get('label'))}</td>"
                    f"<td>{_e(change.get('before'))}</td>"
                    f"<td>{_e(change.get('after'))}</td>"
                    f"<td>{_confidence_badge(change.get('confidence'))}</td>"
                    f"<td>{_source_links(change.get('sources', []))}</td>"
                    "</tr>"
                )
            else:
                row = (
                    "<tr>"
                    f"<td>{_e(change.get('label'))}</td>"
                    f"<td>{_e(change.get('after'))}</td>"
                    f"<td>{_confidence_badge(change.get('confidence'))}</td>"
                    f"<td>{_source_links(change.get('sources', []))}</td>"
                    "</tr>"
                )
                if change.get("kind") == "social":
                    link_rows.append(row)
                else:
                    detail_rows.append(row)

        def table(rows: list[str], empty: str) -> str:
            if not rows:
                return f'<p class="muted">{_e(empty)}</p>'
            return (
                '<div class="table-wrap"><table><thead><tr>'
                "<th>Field</th><th>Added value</th><th>Confidence</th>"
                "<th>Evidence</th></tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></div>"
            )

        def improvement_table(rows: list[str]) -> str:
            if not rows:
                return '<p class="muted">No existing detail fields were changed.</p>'
            return (
                '<div class="table-wrap"><table><thead><tr>'
                "<th>Field</th><th>Previous value</th><th>New value</th>"
                "<th>Confidence</th><th>Evidence</th></tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></div>"
            )

        def candidate_table(rows: list[str]) -> str:
            if not rows:
                return '<p class="muted">No lower-confidence candidates were retained.</p>'
            return (
                '<div class="table-wrap"><table><thead><tr>'
                "<th>Field or link</th><th>Candidate value</th>"
                "<th>Confidence</th><th>Reason and evidence</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table></div>"
            )

        tag_rows = [
            "<tr>"
            f"<td>{_e(tag.get('name'))}</td>"
            f"<td><code>{_e(tag.get('id'))}</code></td>"
            f"<td>{_e(tag.get('summary'))}</td>"
            f"<td>{_confidence_badge(tag.get('confidence', {}).get('score'))}</td>"
            f"<td>{_source_links(tag.get('sources', []))}</td>"
            "</tr>"
            for tag in owner.get("tags", [])
            if isinstance(tag, dict)
        ]
        tag_table = (
            '<div class="table-wrap"><table><thead><tr>'
            "<th>Canonical tag</th><th>Research ID</th><th>Application</th>"
            "<th>Confidence</th><th>Evidence</th></tr></thead><tbody>"
            + "".join(tag_rows)
            + "</tbody></table></div>"
            if tag_rows
            else '<p class="muted">No durable material tags apply.</p>'
        )

        source_items = "".join(
            "<li>"
            f'<a href="{_e(source.get("url"))}" target="_blank" '
            f'rel="noopener noreferrer">{_e(source.get("title"))}</a>'
            f' <span class="muted">— {_e(source.get("publisher"))}, '
            f'Tier {_e(source.get("tier"))}</span>'
            "</li>"
            for source in owner.get("sources", [])
        )
        unresolved = owner.get("unresolved_fields", [])
        owner_source_map = {
            source.get("id"): source
            for source in owner.get("sources", [])
            if isinstance(source, dict)
        }
        candidate_rows = []
        for candidate in owner.get("candidates_requiring_review", []):
            if not isinstance(candidate, dict):
                candidate_rows.append(
                    f'<tr><td colspan="4">{_e(candidate)}</td></tr>'
                )
                continue
            source_refs = [
                owner_source_map[source_id]
                for source_id in candidate.get("source_ids", [])
                if source_id in owner_source_map
            ]
            candidate_rows.append(
                "<tr>"
                f"<td>{_e(candidate.get('field') or candidate.get('type'))}</td>"
                f"<td>{_e(candidate.get('candidate_value') or candidate.get('candidate_url') or candidate.get('value'))}</td>"
                f"<td>{_confidence_badge(candidate.get('confidence', {}).get('score'))}</td>"
                f"<td>{_e(candidate.get('confidence', {}).get('reason'))}<br>"
                f"{_source_links(source_refs)}</td>"
                "</tr>"
            )
        uncertainty_items = "".join(
            f"<li>{_e(item)}</li>" for item in owner.get("uncertainties", [])
        )
        forbes = owner.get("forbes_profile", {})
        forbes_url = forbes.get("url")
        forbes_value = (
            f'<a href="{_e(forbes_url)}" target="_blank" '
            f'rel="noopener noreferrer">{_e(forbes.get("status"))}</a>'
            if forbes_url
            else _e(forbes.get("status"))
        )
        if owner.get("record_type") == "person":
            assessment = owner.get("editorial_assessment") or {}
            assessment_text = ", ".join(
                f"{label}: {_e(assessment.get(field))}/5"
                for field, label in (
                    ("causal_clarity", "causal clarity"),
                    ("human_specificity", "human specificity"),
                    ("durability", "durability"),
                    ("source_invisibility", "source invisibility"),
                    ("natural_voice", "natural voice"),
                    ("reader_orientation", "reader orientation"),
                    (
                        "structural_independence",
                        "structural independence",
                    ),
                )
            )
            editorial_plan = (
                f"Opening: {_e(assessment.get('opening_mode'))}; "
                f"shape: {_e(assessment.get('narrative_shape'))}"
            )
            summary_confidence = _confidence_badge(
                owner.get("biography_confidence")
            )
            biography_comparison = owner.get("biography_comparison")
            comparison_fields = (
                biography_comparison.get("fields")
                if isinstance(biography_comparison, dict)
                else None
            )
            if isinstance(comparison_fields, dict):
                if "biography" in comparison_fields:
                    short_biography_text = _comparison_pair(
                        "biography",
                        comparison_fields["biography"],
                        confidence_score=owner.get(
                            "biography_confidence"
                        ),
                    )
                else:
                    short_biography_text = f"""
                    <h3>Short biography
                      {_confidence_badge(owner.get(
                          "biography_confidence"
                      ))}</h3>
                    <blockquote>{_e(owner.get("biography"))}</blockquote>
                    """
                if "long_biography" in comparison_fields:
                    long_biography_text = _comparison_pair(
                        "long_biography",
                        comparison_fields["long_biography"],
                        confidence_score=owner.get(
                            "long_biography_confidence"
                        ),
                    )
                else:
                    long_biography_text = f"""
                    <h3>Longer biography
                      {_confidence_badge(owner.get(
                          "long_biography_confidence"
                      ))}</h3>
                    <div class="long-biography">
                      {_plain_paragraphs(owner.get("long_biography"))}
                    </div>
                    """
                biography_text = (
                    short_biography_text + long_biography_text
                )
            elif isinstance(biography_comparison, dict):
                before = biography_comparison.get("before", {})
                after = biography_comparison.get("after", {})
                biography_text = f"""
                <h3>Short biography — before and after
                  {_confidence_badge(owner.get("biography_confidence"))}</h3>
                <div class="comparison-grid">
                  <section class="comparison-panel before">
                    <h4>Before</h4>
                    <blockquote>{_e(before.get("biography"))}</blockquote>
                  </section>
                  <section class="comparison-panel after">
                    <h4>After</h4>
                    <blockquote>{_e(after.get("biography"))}</blockquote>
                  </section>
                </div>
                <h3>Longer biography — before and after
                  {_confidence_badge(owner.get(
                      "long_biography_confidence"
                  ))}</h3>
                <div class="comparison-grid">
                  <section class="comparison-panel before">
                    <h4>Before</h4>
                    <div class="long-biography">
                      {_plain_paragraphs(before.get("long_biography"))}
                    </div>
                  </section>
                  <section class="comparison-panel after">
                    <h4>After</h4>
                    <div class="long-biography">
                      {_plain_paragraphs(after.get("long_biography"))}
                    </div>
                  </section>
                </div>
                """
            else:
                biography_text = f"""
                <h3>Short biography
                  {_confidence_badge(owner.get("biography_confidence"))}</h3>
                <blockquote>{_e(owner.get("biography"))}</blockquote>
                <h3>Longer biography
                  {_confidence_badge(owner.get(
                      "long_biography_confidence"
                  ))}</h3>
                <div class="long-biography">
                  {_plain_paragraphs(owner.get("long_biography"))}
                </div>
                """
            biography_review = f"""
                {biography_text}
                <p><strong>Editorial assessment:</strong>
                  {assessment_text}<br>
                  <span class="muted">{editorial_plan}</span><br>
                  <span class="muted">{_e(assessment.get("notes"))}</span></p>
            """
        elif owner.get("record_type") == "institution":
            summary_confidence = _confidence_badge(
                owner.get("biography_confidence")
            )
            editorial_note = owner.get("editorial_note") or {}
            biography_review = f"""
                <h3>Short biography
                  {_confidence_badge(owner.get(
                      "biography_confidence"
                  ))}</h3>
                <blockquote>{_e(owner.get("biography"))}</blockquote>
                <h3>Longer biography
                  {_confidence_badge(owner.get(
                      "long_biography_confidence"
                  ))}</h3>
                <div class="long-biography">
                  {_plain_paragraphs(owner.get("long_biography"))}
                </div>
                <h3>Institution note
                  {_confidence_badge(editorial_note.get(
                      "confidence", {}
                  ).get("score"))}</h3>
                <blockquote>{_e(editorial_note.get("plain_text"))}</blockquote>
            """
        else:
            summary_confidence = (
                '<span class="status">non-person</span>'
            )
            editorial_note = owner.get("editorial_note") or {}
            biography_review = f"""
                <h3>Editorial identity note
                  {_confidence_badge(editorial_note.get(
                      "confidence", {}
                  ).get("score"))}</h3>
                <blockquote>{_e(editorial_note.get("plain_text"))}</blockquote>
                <p class="muted">No biography change is proposed for this
                non-person record.</p>
            """
        biography_comparison = owner.get("biography_comparison")
        wealth_comparison_text = ""
        if isinstance(biography_comparison, dict):
            fields = biography_comparison.get("fields", {})
            if isinstance(fields, dict):
                wealth_comparison_text = "".join(
                    _comparison_pair(field, fields[field])
                    for field in RESEARCH_CLASSIFICATION_FIELDS
                    if field in fields
                )
        comparison_identity = (
            '<p class="comparison-identity"><strong>Changed dossier:</strong> '
            f'Cohort position {_e(owner.get("comparison_cohort_position"))}; '
            f'person ID {_e(owner.get("person_id"))}.</p>'
            if isinstance(biography_comparison, dict)
            else ""
        )
        cards.append(
            f"""
            <details class="owner-card" open>
              <summary>
                <span><span class="rank">{_e(rank_label)}</span>
                {_e(owner.get("display_name"))}</span>
                <span class="summary-badges">
                  {summary_confidence}
                  <span class="status">{_e(owner.get("review_status"))}</span>
                </span>
              </summary>
              <div class="owner-body">
                <p class="vessels">{vessels}</p>
                {comparison_identity}
                {biography_review}
                {wealth_comparison_text}
                <div class="origin">
                  <p><strong>Wealth creation industry:</strong>
                  {_e(owner.get("wealth_creation_industry", {}).get("label"))}
                  {_confidence_badge(owner.get(
                      "wealth_creation_industry", {}
                  ).get("confidence", {}).get("score"))}<br>
                  <span class="muted">{_e(owner.get(
                      "wealth_creation_industry", {}
                  ).get("summary"))}</span></p>
                  <p><strong>Primary industry:</strong>
                  {_e(owner.get("primary_industry", {}).get("label"))}
                  {_confidence_badge(owner.get("primary_industry", {}).get(
                      "confidence", {}
                  ).get("score"))}<br>
                  <span class="muted">{_e(owner.get("primary_industry", {}).get(
                      "summary"
                  ))}</span></p>
                  <p><strong>Wealth origin:</strong>
                  {_e(owner.get("wealth_origin", {}).get("label"))}
                  {_confidence_badge(owner.get("wealth_origin", {}).get(
                      "confidence", {}
                  ).get("score"))}<br>
                  <span class="muted">{_e(owner.get("wealth_origin", {}).get(
                      "summary"
                  ))}</span></p>
                  <p><strong>Relationship to wealth:</strong>
                  {_e(owner.get("wealth_relationship", {}).get("label"))}
                  {_confidence_badge(owner.get("wealth_relationship", {}).get(
                      "confidence", {}
                  ).get("score"))}<br>
                  <span class="muted">{_e(owner.get("wealth_relationship", {}).get(
                      "summary"
                  ))}</span></p>
                </div>
                <p><strong>Forbes profile:</strong> {forbes_value}
                  {_confidence_badge(forbes.get("confidence", {}).get("score"))}</p>
                <h3>Canonical tags</h3>
                {tag_table}
                <h3>Missing fields added</h3>
                {table(detail_rows, "No missing detail fields met the confidence threshold.")}
                <h3>Existing fields improved</h3>
                {improvement_table(improvement_rows)}
                <h3>Links added</h3>
                {table(link_rows, "No missing links met the identity and confidence threshold.")}
                <h3>Needs reviewer judgement</h3>
                {candidate_table(candidate_rows)}
                <p><strong>Unresolved researchable gaps:</strong>
                  {_e(", ".join(unresolved) if unresolved else "None")}</p>
                <details class="evidence">
                  <summary>Evidence and uncertainties</summary>
                  <ul>{source_items}</ul>
                  <ul>{uncertainty_items}</ul>
                </details>
              </div>
            </details>
            """
        )

    rendered = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(report_title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #10141b; --panel: #1b222d; --panel-2: #222c39;
      --text: #edf2f7; --muted: #9eabb9; --accent: #56c2b6;
      --gold: #e5bd6b; --line: #344154; --good: #4fd1a1;
      --warn: #f0b65b; --low: #ef7d7d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background: var(--bg); color: var(--text);
      font: 15px/1.55 Inter, ui-sans-serif, system-ui, sans-serif;
    }}
    main {{ max-width: 1180px; margin: auto; padding: 40px 22px 80px; }}
    h1 {{ margin: 0 0 8px; font-size: clamp(28px, 5vw, 48px); }}
    h2, h3 {{ letter-spacing: .01em; }}
    a {{ color: #82d9d0; }}
    .lede {{ color: var(--muted); max-width: 760px; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px; margin: 26px 0 32px;
    }}
    .metric {{ background: var(--panel); padding: 18px; border-radius: 12px; }}
    .metric strong {{ display: block; font-size: 28px; color: var(--gold); }}
    .owner-card {{
      background: var(--panel); border: 1px solid var(--line);
      border-radius: 14px; margin: 14px 0; overflow: hidden;
    }}
    .owner-card > summary {{
      cursor: pointer; padding: 18px 20px; font-size: 18px; font-weight: 700;
      display: flex; justify-content: space-between; gap: 14px;
      background: var(--panel-2);
    }}
    .owner-body {{ padding: 18px 20px 24px; }}
    .rank {{ color: var(--gold); margin-right: 8px; }}
    .summary-badges {{ display: flex; gap: 8px; align-items: center; }}
    .confidence, .status {{
      display: inline-block; border-radius: 999px; padding: 3px 9px;
      font-size: 12px; font-weight: 800; white-space: nowrap;
    }}
    .confidence.high {{ background: #174f42; color: #8ef0d0; }}
    .confidence.medium {{ background: #5a4219; color: #ffd58c; }}
    .confidence.low {{ background: #5b2929; color: #ffaaaa; }}
    .status {{ background: #303d50; color: #c9d5e4; text-transform: uppercase; }}
    .vessels, .muted {{ color: var(--muted); }}
    blockquote {{
      margin: 12px 0 18px; padding: 16px 18px;
      border-left: 4px solid var(--accent); background: #151b24;
      border-radius: 0 10px 10px 0; font-size: 17px;
    }}
    .long-biography {{
      margin: 12px 0 18px; padding: 14px 18px;
      background: #151b24; border-radius: 10px;
    }}
    .long-biography p:first-child {{ margin-top: 0; }}
    .long-biography p:last-child {{ margin-bottom: 0; }}
    .comparison-grid {{
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px; margin: 12px 0 22px;
    }}
    .comparison-panel {{
      min-width: 0; padding: 14px; border: 1px solid var(--line);
      border-radius: 10px; background: #151b24;
    }}
    .comparison-panel.before {{ border-color: #6b4c4c; }}
    .comparison-panel.after {{ border-color: #276d63; }}
    .comparison-panel h4 {{
      margin: 0 0 10px; color: var(--muted);
      font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
    }}
    .comparison-panel.before h4 {{ color: #e4a5a5; }}
    .comparison-panel.after h4 {{ color: #8ef0d0; }}
    .comparison-panel blockquote {{ margin: 0; height: 100%; }}
    .comparison-panel .long-biography {{ margin: 0; height: 100%; }}
    .comparison-details {{
      display: grid; grid-template-columns: minmax(110px, auto) 1fr;
      gap: 6px 12px; margin: 0;
    }}
    .comparison-details dt {{ color: var(--muted); font-weight: 700; }}
    .comparison-details dd {{ margin: 0; overflow-wrap: anywhere; }}
    .comparison-summary {{
      background: var(--panel); border: 1px solid var(--line);
      border-radius: 14px; margin: 22px 0; padding: 18px 20px;
    }}
    .comparison-summary h2 {{ margin-top: 0; }}
    .comparison-summary-grid {{
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .comparison-identity {{ color: var(--gold); }}
    .origin {{ background: #151b24; padding: 14px; border-radius: 10px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 680px; }}
    th, td {{ padding: 11px; text-align: left; border-bottom: 1px solid var(--line); }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .evidence {{ margin-top: 18px; border-top: 1px solid var(--line); padding-top: 12px; }}
    @media (max-width: 680px) {{
      .metrics {{ grid-template-columns: 1fr; }}
      .comparison-grid {{ grid-template-columns: 1fr; }}
      .comparison-summary-grid {{ grid-template-columns: 1fr; }}
      .owner-card > summary {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{_e(report_title)}</h1>
    <p class="lede">A review-only preview of evidence-backed owner research.
      Selection: {_e(selection_description)}. Source data and live records
      remain unchanged. Generated
      {_e(report.get("generated_at"))}.</p>
    {comparison_summary}
    <section class="metrics">
      <div class="metric"><strong>{len(owners)}</strong>owners researched</div>
      <div class="metric"><strong>{field_additions}</strong>missing fields added</div>
      <div class="metric"><strong>{link_additions}</strong>verified links added</div>
      <div class="metric"><strong>{resolved_tag_count}</strong>resolved tags</div>
      {
        (
          '<div class="metric"><strong>'
          f'{comparison_count}</strong>owners with relevant changes</div>'
        )
        if isinstance(comparison, dict)
        else ""
      }
    </section>
    {"".join(cards)}
  </main>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
