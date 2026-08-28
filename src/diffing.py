from __future__ import annotations

import html
import unicodedata
from collections import Counter
from collections.abc import Collection
from copy import deepcopy
from typing import Any

from .constants import RICH_TEXT_DETAIL_FIELDS
from .tags import TagCatalogue, TagResolutionError, normalize_tag_name


def field_value(field: Any) -> Any:
    if isinstance(field, dict):
        return field.get("value")
    return field


def is_blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def normalize_rich_text_html(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    normalized = html.unescape(value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\xa0", " ")
    return unicodedata.normalize("NFC", normalized).strip()


def detail_values_equal(field: str, left: Any, right: Any) -> bool:
    if field in RICH_TEXT_DETAIL_FIELDS:
        return normalize_rich_text_html(left) == normalize_rich_text_html(right)
    return left == right


def _social_pair(profile: dict[str, Any]) -> tuple[str, str]:
    return str(profile.get("type_id", "")), str(profile.get("url", ""))


def build_owner_change_plan(
    owner: dict[str, Any],
    *,
    live_details: dict[str, Any] | None = None,
    live_socials: list[dict[str, Any]] | None = None,
    allow_clear: bool = False,
    replace_socials: bool = False,
    detail_fields: Collection[str] | None = None,
    include_socials: bool = True,
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

    selected_detail_fields = (
        set(detail_fields) if detail_fields is not None else None
    )
    for key, desired_field in desired_details.items():
        if (
            selected_detail_fields is not None
            and key not in selected_detail_fields
        ):
            continue
        desired_value = field_value(desired_field)
        baseline_field = baseline_details.get(key)
        baseline_value = field_value(baseline_field)
        if detail_values_equal(key, desired_value, baseline_value):
            continue
        if is_blank(desired_value) and not allow_clear:
            skipped_blanks.append(key)
            continue

        if live_details is not None:
            live_value = field_value(live_details.get(key))
            if detail_values_equal(key, live_value, desired_value):
                continue
            if not detail_values_equal(key, live_value, baseline_value):
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

    if include_socials:
        for item in desired_socials:
            key = item.get("profile_key")
            original = baseline_by_key.get(key)
            if original is None:
                social_additions.append(deepcopy(item))
            elif _social_pair(original) != _social_pair(item):
                social_replacements.append(
                    {"from": deepcopy(original), "to": deepcopy(item)}
                )

    if include_socials and replace_socials:
        for key, original in baseline_by_key.items():
            if key not in desired_by_key:
                social_removals.append(deepcopy(original))

    if include_socials and live_socials is not None:
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


def build_tag_change_plan(
    *,
    person_id: int,
    desired_names: Collection[str],
    live_tags: list[dict[str, Any]],
    catalogue: TagCatalogue,
) -> dict[str, Any]:
    """Build a canonical, order-independent owner-tag reconciliation plan."""
    desired_by_id = {}
    desired_order: list[str] = []
    conflicts: list[dict[str, Any]] = []
    for index, name in enumerate(desired_names):
        try:
            canonical = catalogue.resolve(tag_id=None, name=str(name))
        except TagResolutionError as exc:
            conflicts.append(
                {
                    "section": "tags",
                    "field": "desired",
                    "index": index,
                    "value": name,
                    "reason": str(exc),
                }
            )
            continue
        if canonical.id in desired_by_id:
            conflicts.append(
                {
                    "section": "tags",
                    "field": "desired",
                    "index": index,
                    "value": name,
                    "reason": (
                        "duplicate desired canonical tag "
                        f"{canonical.id} ({canonical.name})"
                    ),
                }
            )
            continue
        desired_by_id[canonical.id] = canonical
        desired_order.append(canonical.id)

    normalized_live: dict[str, list[dict[str, str]]] = {}
    association_ids: dict[str, int] = {}
    clean_live: list[dict[str, str]] = []
    for index, raw in enumerate(live_tags):
        association_id = str(raw.get("association_id", "")).strip()
        name = str(raw.get("name", "")).strip()
        if not association_id or not name:
            conflicts.append(
                {
                    "section": "tags",
                    "field": "live",
                    "index": index,
                    "value": deepcopy(raw),
                    "reason": "live tag requires association_id and name",
                }
            )
            continue
        if association_id in association_ids:
            conflicts.append(
                {
                    "section": "tags",
                    "field": "live",
                    "index": index,
                    "value": deepcopy(raw),
                    "reason": (
                        "duplicate live association ID; first seen at index "
                        f"{association_ids[association_id]}"
                    ),
                }
            )
            continue
        association_ids[association_id] = index
        item = {"association_id": association_id, "name": name}
        clean_live.append(item)
        normalized_live.setdefault(normalize_tag_name(name), []).append(item)

    for normalized, items in normalized_live.items():
        if len(items) > 1:
            conflicts.append(
                {
                    "section": "tags",
                    "field": "live",
                    "value": deepcopy(items),
                    "reason": f"duplicate normalized live tag {normalized!r}",
                }
            )

    desired_tags = [
        {"id": desired_by_id[tag_id].id, "name": desired_by_id[tag_id].name}
        for tag_id in desired_order
    ]
    if conflicts:
        return {
            "person_id": person_id,
            "desired_tags": desired_tags,
            "live_tags": clean_live,
            "kept": [],
            "additions": [],
            "removals": [],
            "alias_replacements": [],
            "conflicts": conflicts,
            "has_changes": False,
            "is_exact": False,
        }

    desired_by_normalized = {
        normalize_tag_name(tag.name): tag for tag in desired_by_id.values()
    }
    kept: list[dict[str, str]] = []
    kept_ids: set[str] = set()
    removals: list[dict[str, str]] = []
    alias_replacements: list[dict[str, Any]] = []

    for live in clean_live:
        normalized = normalize_tag_name(live["name"])
        exact = desired_by_normalized.get(normalized)
        if exact is not None:
            kept_ids.add(exact.id)
            kept.append(deepcopy(live))
            continue

        try:
            canonical = catalogue.resolve(tag_id=None, name=live["name"])
        except TagResolutionError:
            canonical = None
        if canonical is not None and canonical.id in desired_by_id:
            replacement = {
                "from": deepcopy(live),
                "to": {
                    "id": canonical.id,
                    "name": canonical.name,
                },
            }
            alias_replacements.append(replacement)
            removals.append(
                {
                    **deepcopy(live),
                    "reason": "replace_alias_with_canonical",
                }
            )
        else:
            removals.append(
                {**deepcopy(live), "reason": "not_in_desired_dossier_tags"}
            )

    additions = [
        {"id": tag.id, "name": tag.name}
        for tag_id in desired_order
        if tag_id not in kept_ids
        for tag in [desired_by_id[tag_id]]
    ]
    removals.sort(key=lambda item: (item["name"].casefold(), item["association_id"]))
    alias_replacements.sort(
        key=lambda item: item["from"]["name"].casefold()
    )
    return {
        "person_id": person_id,
        "desired_tags": desired_tags,
        "live_tags": clean_live,
        "kept": kept,
        "additions": additions,
        "removals": removals,
        "alias_replacements": alias_replacements,
        "conflicts": [],
        "has_changes": bool(additions or removals),
        "is_exact": not additions and not removals,
    }
