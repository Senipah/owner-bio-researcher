from __future__ import annotations

from copy import deepcopy
from typing import Any


DETAIL_SELECT_OPTIONS_LOOKUP = "detail_select_options"

# These controls use the same website vocabulary even though they are stored
# under different field names. Sharing observed legacy values across each
# group lets older enriched documents recover a safer, broader lookup until
# they are refreshed with the complete form options.
EQUIVALENT_SELECT_FIELD_GROUPS = (
    ("nationality", "secondary_nationality"),
    (
        "main_residence_country",
        "secondary_residence_country",
        "birth_country",
    ),
)


def _option_pairs(raw_options: Any, *, context: str) -> list[tuple[str, str]]:
    if isinstance(raw_options, dict):
        items = raw_options.items()
    elif isinstance(raw_options, list):
        items = []
        for index, item in enumerate(raw_options):
            if not isinstance(item, dict):
                raise ValueError(f"{context}[{index}] must be an object")
            items.append((item.get("value"), item.get("label")))
    else:
        raise ValueError(f"{context} must be an object or list")

    pairs: list[tuple[str, str]] = []
    for raw_id, raw_label in items:
        option_id = str(raw_id or "").strip()
        label = str(raw_label or "").strip()
        # Empty IDs are the website's unselected placeholder, not an
        # assignable value.
        if not option_id:
            continue
        if not label:
            raise ValueError(f"{context} option {option_id!r} has no label")
        pairs.append((option_id, label))
    return pairs


def merge_detail_select_option_lookups(
    target: dict[str, dict[str, str]],
    incoming: dict[str, Any],
) -> None:
    """Merge field option maps while rejecting ambiguous website values."""
    if not isinstance(target, dict):
        raise ValueError("detail select option lookup target must be an object")
    if not isinstance(incoming, dict):
        raise ValueError("detail select option lookup must be an object")

    for field, raw_options in incoming.items():
        if not isinstance(field, str) or not field.strip():
            raise ValueError("detail select option field names must be non-empty")
        options = target.setdefault(field, {})
        if not isinstance(options, dict):
            raise ValueError(
                f"detail select option lookup for {field!r} must be an object"
            )
        for option_id, label in _option_pairs(
            raw_options,
            context=f"detail select option lookup {field!r}",
        ):
            existing_label = options.get(option_id)
            if existing_label is not None and existing_label != label:
                raise ValueError(
                    f"detail select option {field!r} ID {option_id!r} maps to "
                    f"both {existing_label!r} and {label!r}"
                )
            conflicting_id = next(
                (
                    known_id
                    for known_id, known_label in options.items()
                    if known_label == label and known_id != option_id
                ),
                None,
            )
            if conflicting_id is not None:
                raise ValueError(
                    f"detail select option {field!r} label {label!r} maps to "
                    f"both {conflicting_id!r} and {option_id!r}"
                )
            options[option_id] = label


def extract_detail_select_option_lookups(
    details: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Extract complete options, or selected legacy values, from details."""
    result: dict[str, dict[str, str]] = {}
    if not isinstance(details, dict):
        return result

    for field, detail in details.items():
        if not isinstance(detail, dict) or detail.get("kind") != "select":
            continue
        raw_options = detail.get("options")
        if raw_options is not None:
            merge_detail_select_option_lookups(
                result,
                {field: raw_options},
            )

        option_id = str(detail.get("option_id") or "").strip()
        option_label = str(
            detail.get("option_label") or detail.get("value") or ""
        ).strip()
        if option_id and option_label:
            merge_detail_select_option_lookups(
                result,
                {field: {option_id: option_label}},
            )
    return result


def strip_detail_select_options(details: dict[str, Any]) -> None:
    """Remove repeated full option lists before details are persisted."""
    if not isinstance(details, dict):
        return
    for detail in details.values():
        if isinstance(detail, dict) and detail.get("kind") == "select":
            detail.pop("options", None)


def merge_document_detail_select_options(
    document: dict[str, Any],
    incoming: dict[str, Any],
) -> None:
    lookups = document.setdefault("lookups", {})
    if not isinstance(lookups, dict):
        raise ValueError("owner document lookups must be an object")
    target = lookups.setdefault(DETAIL_SELECT_OPTIONS_LOOKUP, {})
    if not isinstance(target, dict):
        raise ValueError(
            f"lookups.{DETAIL_SELECT_OPTIONS_LOOKUP} must be an object"
        )
    merge_detail_select_option_lookups(target, incoming)


def build_detail_select_option_lookups(
    document: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Return system-derived select values, including a legacy fallback."""
    result: dict[str, dict[str, str]] = {}
    lookups = document.get("lookups", {})
    if lookups is not None and not isinstance(lookups, dict):
        raise ValueError("owner document lookups must be an object")
    if isinstance(lookups, dict):
        stored = lookups.get(DETAIL_SELECT_OPTIONS_LOOKUP)
        if stored is not None:
            merge_detail_select_option_lookups(result, stored)

    owners = document.get("owners", [])
    if not isinstance(owners, list):
        raise ValueError("owner document owners must be an array")
    for owner in owners:
        if not isinstance(owner, dict):
            continue
        merge_detail_select_option_lookups(
            result,
            extract_detail_select_option_lookups(owner.get("details", {})),
        )

    for equivalent_fields in EQUIVALENT_SELECT_FIELD_GROUPS:
        combined: dict[str, dict[str, str]] = {}
        for field in equivalent_fields:
            options = result.get(field)
            if options:
                merge_detail_select_option_lookups(
                    combined,
                    {"combined": options},
                )
        shared = combined.get("combined")
        if not shared:
            continue
        for field in equivalent_fields:
            merge_detail_select_option_lookups(result, {field: shared})
    return result


def resolve_detail_select_option_id(
    lookups: dict[str, dict[str, str]],
    field: str,
    label: Any,
) -> str:
    if not isinstance(label, str) or not label.strip():
        raise ValueError(
            f"select field {field!r} requires a non-empty system option label"
        )
    options = lookups.get(field)
    if not isinstance(options, dict) or not options:
        raise ValueError(
            f"no system option lookup is available for select field {field!r}"
        )
    matches = [option_id for option_id, option_label in options.items()
               if option_label == label]
    if not matches:
        raise ValueError(
            f"{label!r} is not a valid system option for select field {field!r}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"system option label {label!r} is ambiguous for select field {field!r}"
        )
    return matches[0]


def copy_relevant_detail_select_option_lookups(
    document: dict[str, Any],
    details: dict[str, Any],
) -> dict[str, dict[str, str]]:
    catalogue = build_detail_select_option_lookups(document)
    return {
        field: deepcopy(catalogue[field])
        for field, detail in details.items()
        if isinstance(detail, dict)
        and detail.get("kind") == "select"
        and field in catalogue
    }
