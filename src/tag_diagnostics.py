from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Iterable

from .tags import TagCatalogue, normalize_tag_name


DIMENSION_FACETS = {
    "company": "company_affiliation",
    "occupation": "profession_or_role",
    "industry": "industry",
    "subindustry": "industry",
    "investment": "investment_background",
    "sport": "sporting_identity",
    "royal family": "family_or_royal_affiliation",
    "dynasty": "family_or_royal_affiliation",
    "business family": "family_or_royal_affiliation",
    "family": "family_or_royal_affiliation",
    "public office": "public_office",
    "cultural interest": "cultural_interest",
}
TRANSITION_WORDS = {
    "after",
    "before",
    "during",
    "evolved",
    "evolving",
    "expansion",
    "led",
    "progression",
    "succession",
    "transition",
    "transformation",
}


def _dimension(tag_facets: Iterable[str]) -> str | None:
    dimensions = {
        DIMENSION_FACETS[facet.casefold()]
        for facet in tag_facets
        if facet.casefold() in DIMENSION_FACETS
    }
    return sorted(dimensions)[0] if len(dimensions) == 1 else None


def _sentence_like(name: str) -> bool:
    words = normalize_tag_name(name).split()
    return len(words) >= 7 or (
        len(words) >= 4 and bool(set(words) & TRANSITION_WORDS)
    )


def build_tag_governance_diagnostics(
    targets: list[dict[str, Any]],
    catalogue: TagCatalogue,
    *,
    low_record_count: int = 5,
    high_record_count: int = 50,
    high_assignment_count: int = 12,
) -> dict[str, Any]:
    """Return review signals only; never mutate targets or the catalogue."""
    cohorts: dict[str, set[int]] = defaultdict(set)
    for target in targets:
        person_id = target["person_id"]
        for assignment in target.get("desired_tags", []):
            cohorts[assignment["id"]].add(person_id)

    active_frequency = []
    for tag_id, tag in sorted(catalogue.tags_by_id.items()):
        count = len(cohorts.get(tag_id, set()))
        if count < low_record_count or count > high_record_count:
            active_frequency.append(
                {
                    "severity": "warning",
                    "tag_id": tag_id,
                    "name": tag.name,
                    "dossier_record_count": count,
                    "signal": (
                        "below_soft_range"
                        if count < low_record_count
                        else "above_soft_range"
                    ),
                }
            )

    high_assignment_records = [
        {
            "severity": "warning",
            "person_id": target["person_id"],
            "display_name": target.get("display_name", ""),
            "active_assignment_count": len(target.get("desired_tags", [])),
        }
        for target in targets
        if len(target.get("desired_tags", [])) > high_assignment_count
    ]

    dimension_overlaps = []
    for target in targets:
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for assignment in target.get("desired_tags", []):
            tag = catalogue.tags_by_id.get(assignment["id"])
            if tag is None:
                continue
            dimension = _dimension(tag.facets)
            if dimension is not None:
                grouped[dimension].append(
                    {"id": tag.id, "name": tag.name}
                )
        for dimension, assignments in sorted(grouped.items()):
            if len(assignments) > 2:
                dimension_overlaps.append(
                    {
                        "severity": "warning",
                        "person_id": target["person_id"],
                        "display_name": target.get("display_name", ""),
                        "dimension": dimension,
                        "assignments": assignments,
                    }
                )

    active_tags = sorted(catalogue.tags_by_id.values(), key=lambda item: item.id)
    near_identical_names = []
    for index, left in enumerate(active_tags):
        for right in active_tags[index + 1 :]:
            ratio = SequenceMatcher(
                None,
                left.normalized_name,
                right.normalized_name,
            ).ratio()
            if ratio >= 0.9:
                near_identical_names.append(
                    {
                        "severity": "warning",
                        "left": {"id": left.id, "name": left.name},
                        "right": {"id": right.id, "name": right.name},
                        "similarity": round(ratio, 3),
                    }
                )

    cohort_groups: dict[tuple[int, ...], list[str]] = defaultdict(list)
    for tag_id, person_ids in cohorts.items():
        if person_ids:
            cohort_groups[tuple(sorted(person_ids))].append(tag_id)
    identical_cohorts = []
    for person_ids, tag_ids in sorted(cohort_groups.items()):
        if len(tag_ids) < 2:
            continue
        identical_cohorts.append(
            {
                "severity": "warning",
                "person_ids": list(person_ids),
                "dossier_record_count": len(person_ids),
                "tags": [
                    {
                        "id": tag_id,
                        "name": catalogue.tags_by_id[tag_id].name,
                    }
                    for tag_id in sorted(tag_ids)
                ],
            }
        )

    non_active_references = [
        {
            "severity": "warning",
            "person_id": target["person_id"],
            "display_name": target.get("display_name", ""),
            **reference,
        }
        for target in targets
        for reference in target.get("non_active_tag_references", [])
    ]

    candidate_active_duplicates = []
    for target in targets:
        for index, candidate in enumerate(target.get("candidate_concepts", [])):
            if not isinstance(candidate, dict):
                continue
            name = str(candidate.get("proposed_name", "")).strip()
            if not name:
                continue
            inspection = catalogue.inspect(tag_id=None, name=name)
            canonical = inspection.get("canonical")
            if inspection.get("status") in {"active", "merged"}:
                candidate_active_duplicates.append(
                    {
                        "severity": "warning",
                        "person_id": target["person_id"],
                        "display_name": target.get("display_name", ""),
                        "candidate_index": index,
                        "proposed_name": name,
                        "active_tag": {
                            "id": canonical.id,
                            "name": canonical.name,
                        },
                    }
                )

    sentence_like_names = [
        {
            "severity": "warning",
            "tag_id": tag.id,
            "name": tag.name,
            "status": tag.status,
        }
        for tag in sorted(
            catalogue.all_tags_by_id.values(), key=lambda item: item.id
        )
        if _sentence_like(tag.name)
    ]

    categories = {
        "active_frequency_outliers": active_frequency,
        "high_assignment_records": high_assignment_records,
        "semantic_dimension_overlaps": dimension_overlaps,
        "near_identical_active_names": near_identical_names,
        "identical_active_cohorts": identical_cohorts,
        "non_active_dossier_references": non_active_references,
        "candidate_concepts_matching_active_labels": candidate_active_duplicates,
        "sentence_or_transition_style_names": sentence_like_names,
    }
    return {
        "mode": "diagnostic_warnings_only",
        "automatic_edits": False,
        "count_semantics": "source dossier records, not unique people",
        "soft_frequency_range": {
            "minimum": low_record_count,
            "maximum": high_record_count,
            "approval_effect": "none",
        },
        "warning_counts": {
            name: len(items) for name, items in categories.items()
        },
        **categories,
    }
