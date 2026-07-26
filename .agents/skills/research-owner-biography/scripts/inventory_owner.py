from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_PRIORITY_SOCIALS = ("Instagram", "LinkedIn", "Personal Website")
PERSON_RELEVANT_SOCIALS = {
    "Facebook",
    "Twitter",
    "Youtube",
    "LinkedIn",
    "Instagram",
    "Personal Website",
    "TikTok",
}
CALCULATED_OR_SYSTEM_FIELDS = {
    "birth_age",
    "birth_age_at_date",
    "death_age",
    "death_age_at_date",
    "internal_notes",
    "unknown_name",
}
OPTIONAL_IDENTITY_FIELDS = {
    "title",
    "name_suffix",
    "secondary_residence_country",
}
CONDITIONAL_DEATH_FIELDS = {
    "death_day",
    "death_month",
    "death_year",
    "death_age",
    "death_age_at_date",
}


def _normalise_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _detail_value(owner: dict[str, Any], field: str) -> Any:
    detail = owner.get("details", {}).get(field)
    if isinstance(detail, dict):
        return detail.get("value")
    return detail


def _display_name(owner: dict[str, Any]) -> str:
    value = _detail_value(owner, "display_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    report = owner.get("report")
    if isinstance(report, dict):
        name = " ".join(
            str(report.get(key, "")).strip()
            for key in ("first_name", "last_name")
            if str(report.get(key, "")).strip()
        )
        if name:
            return name
    return str(owner.get("person_id", "Unknown owner"))


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _find_owner(
    owners: list[dict[str, Any]],
    person_id: int | None,
    name: str | None,
) -> dict[str, Any]:
    if person_id is not None:
        matches = [owner for owner in owners if owner.get("person_id") == person_id]
    else:
        target = _normalise_name(name or "")
        exact = [
            owner
            for owner in owners
            if _normalise_name(_display_name(owner)) == target
        ]
        matches = exact or [
            owner
            for owner in owners
            if target in _normalise_name(_display_name(owner))
        ]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        criterion = f"person_id={person_id}" if person_id is not None else f"name={name!r}"
        raise ValueError(f"no owner matched {criterion}")
    candidates = [
        {"person_id": owner.get("person_id"), "display_name": _display_name(owner)}
        for owner in matches
    ]
    raise ValueError(
        "owner match is ambiguous: "
        + json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
    )


def _social_lookup(document: dict[str, Any]) -> dict[str, str]:
    lookup = document.get("lookups", {}).get("social_media_types", {})
    if not isinstance(lookup, dict):
        return {}
    return {
        str(type_id): str(label)
        for type_id, label in lookup.items()
        if str(type_id).strip() and str(label).strip()
    }


def build_inventory(
    document: dict[str, Any],
    owner: dict[str, Any],
    source_path: str,
    priority_socials: tuple[str, ...] = DEFAULT_PRIORITY_SOCIALS,
) -> dict[str, Any]:
    details = owner.get("details")
    if not isinstance(details, dict):
        raise ValueError("matched owner has no details object")

    mortality = str(_detail_value(owner, "mortality_status") or "").casefold()
    blank_details: list[dict[str, Any]] = []
    researchable: list[str] = []
    optional: list[str] = []
    inapplicable_or_system: list[str] = []

    for field, detail in details.items():
        value = detail.get("value") if isinstance(detail, dict) else detail
        if not _is_blank(value):
            continue
        item = {
            "field": field,
            "label": detail.get("label", field) if isinstance(detail, dict) else field,
            "kind": detail.get("kind") if isinstance(detail, dict) else None,
        }
        if field in CONDITIONAL_DEATH_FIELDS and mortality == "alive":
            item["category"] = "not_applicable_while_alive"
            inapplicable_or_system.append(field)
        elif field in CALCULATED_OR_SYSTEM_FIELDS:
            item["category"] = "calculated_or_system"
            inapplicable_or_system.append(field)
        elif field in OPTIONAL_IDENTITY_FIELDS:
            item["category"] = "optional"
            optional.append(field)
        else:
            item["category"] = "researchable"
            researchable.append(field)
        blank_details.append(item)

    lookup = _social_lookup(document)
    profiles = owner.get("social_media_profiles")
    if not isinstance(profiles, list):
        profiles = []
    existing_socials = [
        {
            "type_id": str(profile.get("type_id", "")),
            "type": profile.get("type"),
            "url": profile.get("url"),
        }
        for profile in profiles
        if isinstance(profile, dict)
    ]
    existing_types = {
        str(profile.get("type", "")).casefold()
        for profile in existing_socials
        if profile.get("type")
    }
    missing_supported = [
        {"type_id": type_id, "type": label}
        for type_id, label in lookup.items()
        if label.casefold() not in existing_types
    ]
    priority_keys = {label.casefold() for label in priority_socials}

    return {
        "source_path": source_path.replace("\\", "/"),
        "owner": {
            "person_id": owner.get("person_id"),
            "display_name": _display_name(owner),
            "profile_url": owner.get("profile_url"),
            "top_100": owner.get("top_100"),
        },
        "raw_blank_details": blank_details,
        "researchable_missing_details": researchable,
        "optional_missing_details": optional,
        "inapplicable_or_system_details": inapplicable_or_system,
        "biography_present": not _is_blank(_detail_value(owner, "biography")),
        "existing_socials": existing_socials,
        "missing_priority_social_types": [
            item for item in missing_supported if item["type"].casefold() in priority_keys
        ],
        "missing_person_relevant_social_types": [
            item for item in missing_supported if item["type"] in PERSON_RELEVANT_SOCIALS
        ],
        "missing_supported_social_types": missing_supported,
        "social_type_lookup": lookup,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only inventory of missing fields and link types for one owner."
    )
    parser.add_argument("--input", required=True, type=Path)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--person-id", type=int)
    target.add_argument("--name")
    parser.add_argument(
        "--priority-social",
        action="append",
        dest="priority_socials",
        help="Priority social label; repeat to specify multiple labels.",
    )
    args = parser.parse_args()

    try:
        document = json.loads(args.input.read_text(encoding="utf-8"))
        owners = document.get("owners")
        if not isinstance(owners, list):
            raise ValueError("input document has no owners list")
        owner = _find_owner(owners, args.person_id, args.name)
        priority_socials = tuple(args.priority_socials or DEFAULT_PRIORITY_SOCIALS)
        inventory = build_inventory(
            document,
            owner,
            str(args.input),
            priority_socials,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Inventory failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(inventory, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
