from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


def field_value(field: Any) -> Any:
    if isinstance(field, dict):
        return field.get("value")
    return field


def is_blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def _social_pair(profile: dict[str, Any]) -> tuple[str, str]:
    return str(profile.get("type_id", "")), str(profile.get("url", ""))


def build_owner_change_plan(
    owner: dict[str, Any],
    *,
    live_details: dict[str, Any] | None = None,
    live_socials: list[dict[str, Any]] | None = None,
    allow_clear: bool = False,
    replace_socials: bool = False,
) -> dict[str, Any]:
    baseline = owner.get("_baseline")
    if not isinstance(baseline, dict):
        raise ValueError(
            f"Owner {owner.get('person_id')} has no enrichment baseline"
        )

    desired_details = owner.get("details", {})
    baseline_details = baseline.get("details", {})
    detail_changes: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    skipped_blanks: list[str] = []

    for key, desired_field in desired_details.items():
        desired_value = field_value(desired_field)
        baseline_field = baseline_details.get(key)
        baseline_value = field_value(baseline_field)
        if desired_value == baseline_value:
            continue
        if is_blank(desired_value) and not allow_clear:
            skipped_blanks.append(key)
            continue

        if live_details is not None:
            live_value = field_value(live_details.get(key))
            if live_value == desired_value:
                continue
            if live_value != baseline_value:
                conflicts.append(
                    {
                        "section": "details",
                        "field": key,
                        "baseline": baseline_value,
                        "live": live_value,
                        "desired": desired_value,
                    }
                )
                continue

        detail_changes.append(
            {
                "field": key,
                "from": baseline_value,
                "to": desired_value,
                "desired_field": deepcopy(desired_field),
            }
        )

    baseline_socials = baseline.get("social_media_profiles", [])
    desired_socials = owner.get("social_media_profiles", [])
    baseline_by_key = {
        item.get("profile_key"): item
        for item in baseline_socials
        if item.get("profile_key")
    }
    desired_by_key = {
        item.get("profile_key"): item
        for item in desired_socials
        if item.get("profile_key")
    }

    social_additions: list[dict[str, Any]] = []
    social_replacements: list[dict[str, Any]] = []
    social_removals: list[dict[str, Any]] = []

    for item in desired_socials:
        key = item.get("profile_key")
        original = baseline_by_key.get(key)
        if original is None:
            social_additions.append(deepcopy(item))
        elif _social_pair(original) != _social_pair(item):
            social_replacements.append(
                {"from": deepcopy(original), "to": deepcopy(item)}
            )

    if replace_socials:
        for key, original in baseline_by_key.items():
            if key not in desired_by_key:
                social_removals.append(deepcopy(original))

    if live_socials is not None:
        live_pairs = [_social_pair(item) for item in live_socials]
        desired_pairs = [_social_pair(item) for item in desired_socials]
        baseline_pairs = [_social_pair(item) for item in baseline_socials]

        social_additions = [
            item for item in social_additions if _social_pair(item) not in live_pairs
        ]
        verified_replacements: list[dict[str, Any]] = []
        for replacement in social_replacements:
            old_pair = _social_pair(replacement["from"])
            new_pair = _social_pair(replacement["to"])
            if new_pair in live_pairs and old_pair not in live_pairs:
                continue
            if old_pair not in live_pairs:
                conflicts.append(
                    {
                        "section": "social_media_profiles",
                        "profile_key": replacement["from"].get("profile_key"),
                        "baseline": replacement["from"],
                        "live": live_socials,
                        "desired": replacement["to"],
                    }
                )
                continue
            verified_replacements.append(replacement)
        social_replacements = verified_replacements
        social_removals = [
            item for item in social_removals if _social_pair(item) in live_pairs
        ]

        live_counts = Counter(live_pairs)
        baseline_counts = Counter(baseline_pairs)
        desired_counts = Counter(desired_pairs)
        if replace_socials and live_counts not in (
            baseline_counts,
            desired_counts,
        ):
            conflicts.append(
                {
                    "section": "social_media_profiles",
                    "field": "*",
                    "baseline": baseline_socials,
                    "live": live_socials,
                    "desired": desired_socials,
                }
            )
            social_additions = []
            social_replacements = []
            social_removals = []

    return {
        "person_id": owner.get("person_id"),
        "detail_changes": detail_changes,
        "social_additions": social_additions,
        "social_replacements": social_replacements,
        "social_removals": social_removals,
        "skipped_blank_fields": skipped_blanks,
        "conflicts": conflicts,
        "has_changes": bool(
            detail_changes
            or social_additions
            or social_replacements
            or social_removals
        ),
    }
