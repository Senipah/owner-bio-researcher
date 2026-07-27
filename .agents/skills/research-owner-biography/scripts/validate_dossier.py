from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inventory_owner import _find_owner, build_inventory


CONFIDENCE_BANDS = (
    (95, 100, "very_high"),
    (85, 94, "high"),
    (70, 84, "medium"),
    (50, 69, "low"),
    (0, 49, "insufficient"),
)
RESEARCH_STATUSES = {
    "complete",
    "limited",
    "identity_conflict",
    "insufficient_evidence",
}
FORBES_STATUSES = {"verified", "not_found", "ambiguous", "unavailable"}
REVIEW_STATUSES = {"pending", "approved", "rejected"}
PRIMARY_INDUSTRIES = {
    "automotive": "Automotive",
    "construction_engineering": "Construction & Engineering",
    "diversified": "Diversified",
    "energy": "Energy",
    "fashion_retail": "Fashion & Retail",
    "finance_investments": "Finance & Investments",
    "food_beverage": "Food & Beverage",
    "gambling_casinos": "Gambling & Casinos",
    "healthcare": "Healthcare",
    "logistics": "Logistics",
    "manufacturing": "Manufacturing",
    "media_entertainment": "Media & Entertainment",
    "metals_mining": "Metals & Mining",
    "real_estate": "Real Estate",
    "service": "Service",
    "sports": "Sports",
    "technology": "Technology",
    "telecom": "Telecom",
    "shipping_maritime": "Shipping & Maritime",
    "aviation_aerospace": "Aviation & Aerospace",
    "hospitality": "Hospitality",
    "agriculture": "Agriculture",
    "unknown": "Unknown",
}
WEALTH_ORIGINS = {
    "self_made": "Self-made",
    "inherited": "Inherited",
    "inherited_and_expanded": "Inherited and expanded",
    "dynastic_royal": "Dynastic / royal",
    "marriage_family_transfer": "Marriage / family transfer",
    "mixed": "Mixed",
    "unknown": "Unknown",
}
WEALTH_RELATIONSHIPS = {
    "founder": "Founder",
    "operator": "Operator",
    "investor": "Investor",
    "heir_family_shareholder": "Heir / family shareholder",
    "family_office_principal": "Family office principal",
    "royal_beneficiary": "Royal beneficiary",
    "trustee_custodian": "Trustee or custodian",
    "passive_asset_owner": "Passive asset owner",
    "unknown": "Unknown",
}
CLASSIFICATION_FIELDS = {
    "primary_industry": PRIMARY_INDUSTRIES,
    "wealth_origin": WEALTH_ORIGINS,
    "wealth_relationship": WEALTH_RELATIONSHIPS,
}
WORD_PATTERN = re.compile(r"\b[\w]+(?:[’'-][\w]+)*\b")


def _confidence(
    value: Any,
    path: str,
    errors: list[str],
) -> int | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    score = value.get("score")
    band = value.get("band")
    reason = value.get("reason")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        errors.append(f"{path}.score must be an integer from 0 to 100")
        return None
    expected = next(
        name for minimum, maximum, name in CONFIDENCE_BANDS
        if minimum <= score <= maximum
    )
    if band != expected:
        errors.append(f"{path}.band must be {expected!r} for score {score}")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(f"{path}.reason must be non-empty")
    return score


def _url(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{path} must be an HTTP(S) URL")
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{path} must be an HTTP(S) URL")


def _source_ids(
    value: Any,
    path: str,
    known: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{path} must be a non-empty list")
        return
    unknown = [item for item in value if item not in known]
    if unknown:
        errors.append(f"{path} contains unknown source IDs: {unknown}")


def _classification(
    value: Any,
    path: str,
    choices: dict[str, str],
    known_sources: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return
    classification = value.get("classification")
    if classification not in choices:
        errors.append(f"{path}.classification is invalid")
    elif value.get("label") != choices[classification]:
        errors.append(
            f"{path}.label must be {choices[classification]!r} for "
            f"classification {classification!r}"
        )
    if not isinstance(value.get("summary"), str) or not value["summary"].strip():
        errors.append(f"{path}.summary must be non-empty")
    score = _confidence(value.get("confidence"), f"{path}.confidence", errors)
    if (
        score is not None
        and classification in choices
        and classification != "unknown"
        and score < 85
    ):
        errors.append(
            f"{path} must use classification 'unknown' below confidence 85"
        )
    _source_ids(
        value.get("source_ids"),
        f"{path}.source_ids",
        known_sources,
        errors,
    )


def validate(document: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return ["dossier root must be an object"], warnings

    required = {
        "schema_version",
        "owner",
        "input_snapshot",
        "research_status",
        "forbes_profile",
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
        "biography",
        "long_biography",
        "proposed_details",
        "proposed_socials",
        "candidates_requiring_review",
        "sources",
        "uncertainties",
        "review",
    }
    missing = sorted(required - document.keys())
    if missing:
        errors.append(f"missing top-level keys: {missing}")

    if document.get("schema_version") != 4:
        errors.append("schema_version must be 4")
    if document.get("research_status") not in RESEARCH_STATUSES:
        errors.append("research_status is invalid")

    owner = document.get("owner")
    if not isinstance(owner, dict):
        errors.append("owner must be an object")
    else:
        if not isinstance(owner.get("display_name"), str) or not owner["display_name"].strip():
            errors.append("owner.display_name must be non-empty")
        _confidence(
            owner.get("identity_confidence"),
            "owner.identity_confidence",
            errors,
        )

    snapshot = document.get("input_snapshot")
    researchable_missing: set[str] = set()
    raw_blank: set[str] = set()
    existing_social_types: set[str] = set()
    social_lookup: dict[str, str] = {}
    if not isinstance(snapshot, dict):
        errors.append("input_snapshot must be an object")
    else:
        if not isinstance(snapshot.get("source_path"), str) or not snapshot["source_path"].strip():
            errors.append("input_snapshot.source_path must be non-empty")
        for key in (
            "raw_blank_details",
            "researchable_missing_details",
            "optional_missing_details",
            "inapplicable_or_system_details",
            "existing_social_types",
            "missing_priority_social_types",
        ):
            value = snapshot.get(key)
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                errors.append(f"input_snapshot.{key} must be a list of strings")
        raw_blank = set(snapshot.get("raw_blank_details", []))
        researchable_missing = set(snapshot.get("researchable_missing_details", []))
        existing_social_types = {
            item.casefold() for item in snapshot.get("existing_social_types", [])
            if isinstance(item, str)
        }
        lookup = snapshot.get("social_type_lookup")
        if not isinstance(lookup, dict) or any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
            for key, value in (lookup.items() if isinstance(lookup, dict) else [])
        ):
            errors.append("input_snapshot.social_type_lookup must map IDs to labels")
        else:
            social_lookup = lookup
        if not researchable_missing <= raw_blank:
            errors.append(
                "input_snapshot.researchable_missing_details must be raw blanks"
            )

    sources = document.get("sources")
    known_sources: set[str] = set()
    if not isinstance(sources, list):
        errors.append("sources must be a list")
        sources = []
    for index, source in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{path} must be an object")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"{path}.id must be non-empty")
        elif source_id in known_sources:
            errors.append(f"{path}.id is duplicated: {source_id}")
        else:
            known_sources.add(source_id)
        _url(source.get("url"), f"{path}.url", errors)
        if source.get("tier") not in {1, 2, 3, 4}:
            errors.append(f"{path}.tier must be 1, 2, 3, or 4")
        for key in ("title", "publisher", "accessed_at"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                errors.append(f"{path}.{key} must be non-empty")
        if not isinstance(source.get("supports"), list) or not source["supports"]:
            errors.append(f"{path}.supports must be a non-empty list")

    forbes = document.get("forbes_profile")
    if not isinstance(forbes, dict):
        errors.append("forbes_profile must be an object")
    else:
        status = forbes.get("status")
        if status not in FORBES_STATUSES:
            errors.append("forbes_profile.status is invalid")
        if status == "verified":
            _url(forbes.get("url"), "forbes_profile.url", errors)
            hostname = urlparse(str(forbes.get("url", ""))).hostname or ""
            if hostname != "forbes.com" and not hostname.endswith(".forbes.com"):
                errors.append("verified Forbes URL must use forbes.com")
        elif forbes.get("url") is not None:
            warnings.append("non-verified Forbes status normally has a null URL")
        _confidence(forbes.get("confidence"), "forbes_profile.confidence", errors)

    for field, choices in CLASSIFICATION_FIELDS.items():
        _classification(
            document.get(field),
            field,
            choices,
            known_sources,
            errors,
        )

    biography = document.get("biography")
    if not isinstance(biography, dict):
        errors.append("biography must be an object")
    else:
        plain = biography.get("plain_text")
        if not isinstance(plain, str) or not plain.strip():
            errors.append("biography.plain_text must be non-empty")
        else:
            count = len(WORD_PATTERN.findall(plain))
            if biography.get("word_count") != count:
                errors.append(
                    f"biography.word_count must be {count}, not "
                    f"{biography.get('word_count')!r}"
                )
            if not 50 <= count <= 55:
                errors.append("biography must contain 50-55 words")
            if "\n" in plain or "\r" in plain:
                errors.append("biography.plain_text must be one paragraph")
            expected_html = f"<p>{html.escape(plain, quote=False)}</p>\r\n"
            if biography.get("html") != expected_html:
                errors.append("biography.html is not canonical CKEditor HTML")
        _confidence(biography.get("confidence"), "biography.confidence", errors)
        _source_ids(
            biography.get("source_ids"),
            "biography.source_ids",
            known_sources,
            errors,
        )

    long_biography = document.get("long_biography")
    if not isinstance(long_biography, dict):
        errors.append("long_biography must be an object")
    else:
        long_plain = long_biography.get("plain_text")
        if not isinstance(long_plain, str) or not long_plain.strip():
            errors.append("long_biography.plain_text must be non-empty")
        else:
            count = len(WORD_PATTERN.findall(long_plain))
            if long_biography.get("word_count") != count:
                errors.append(
                    f"long_biography.word_count must be {count}, not "
                    f"{long_biography.get('word_count')!r}"
                )
            if not 90 <= count <= 190:
                errors.append("long_biography must contain 90-190 words")
            elif not 120 <= count <= 170:
                warnings.append(
                    "long_biography is outside the preferred 120-170 words"
                )
            if "\r" in long_plain:
                errors.append(
                    "long_biography.plain_text must use LF paragraph separators"
                )
            paragraphs = long_plain.split("\n\n")
            if (
                len(paragraphs) != 2
                or any(
                    not paragraph.strip() or "\n" in paragraph
                    for paragraph in paragraphs
                )
            ):
                errors.append(
                    "long_biography.plain_text must contain exactly two "
                    "paragraphs"
                )
            else:
                expected_html = "".join(
                    f"<p>{html.escape(paragraph, quote=False)}</p>\r\n"
                    for paragraph in paragraphs
                )
                if long_biography.get("html") != expected_html:
                    errors.append(
                        "long_biography.html is not canonical CKEditor HTML"
                    )
            if (
                isinstance(biography, dict)
                and long_plain == biography.get("plain_text")
            ):
                errors.append(
                    "long_biography must not repeat biography verbatim"
                )
        _confidence(
            long_biography.get("confidence"),
            "long_biography.confidence",
            errors,
        )
        _source_ids(
            long_biography.get("source_ids"),
            "long_biography.source_ids",
            known_sources,
            errors,
        )

    for collection in ("proposed_details", "proposed_socials"):
        items = document.get(collection)
        if not isinstance(items, list):
            errors.append(f"{collection} must be a list")
            continue
        for index, item in enumerate(items):
            path = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path} must be an object")
                continue
            score = _confidence(item.get("confidence"), f"{path}.confidence", errors)
            if score is not None and score < 85:
                errors.append(f"{path} confidence must be at least 85")
            _source_ids(
                item.get("source_ids"),
                f"{path}.source_ids",
                known_sources,
                errors,
            )
            if collection == "proposed_details":
                if not isinstance(item.get("field"), str) or not item["field"].strip():
                    errors.append(f"{path}.field must be non-empty")
                if "value" not in item:
                    errors.append(f"{path}.value is required")
                action = item.get("action")
                if action not in {"fill_missing", "correct_existing"}:
                    errors.append(
                        f"{path}.action must be 'fill_missing' or 'correct_existing'"
                    )
                elif action == "fill_missing" and item.get("field") not in researchable_missing:
                    errors.append(
                        f"{path}.field is not a researchable missing input field"
                    )
                elif action == "correct_existing":
                    if "existing_value" not in item:
                        errors.append(
                            f"{path}.existing_value is required for a correction"
                        )
                    if item.get("field") in raw_blank:
                        errors.append(
                            f"{path}.field is blank; use action 'fill_missing'"
                        )
                classification_field = item.get("field")
                if classification_field in CLASSIFICATION_FIELDS:
                    classification_value = document.get(classification_field, {})
                    if item.get("value") != classification_value.get("label"):
                        errors.append(
                            f"{path}.value must match "
                            f"{classification_field}.label"
                        )
                    if classification_value.get("classification") == "unknown":
                        errors.append(
                            f"{path} must not propose an Unknown classification"
                        )
                    if item.get("confidence") != classification_value.get("confidence"):
                        errors.append(
                            f"{path}.confidence must match "
                            f"{classification_field}.confidence"
                        )
                    if item.get("source_ids") != classification_value.get("source_ids"):
                        errors.append(
                            f"{path}.source_ids must match "
                            f"{classification_field}.source_ids"
                        )
            else:
                if not isinstance(item.get("type"), str) or not item["type"].strip():
                    errors.append(f"{path}.type must be non-empty")
                type_id = item.get("type_id")
                if not isinstance(type_id, str) or not type_id.strip():
                    errors.append(f"{path}.type_id must be non-empty")
                elif social_lookup.get(type_id) != item.get("type"):
                    errors.append(f"{path}.type_id does not match the input lookup")
                if (
                    isinstance(item.get("type"), str)
                    and item["type"].casefold() in existing_social_types
                ):
                    errors.append(f"{path}.type already exists in the input record")
                _url(item.get("url"), f"{path}.url", errors)
                if not isinstance(item.get("verification"), str) or not item["verification"].strip():
                    errors.append(f"{path}.verification must be non-empty")

    for key in ("candidates_requiring_review", "uncertainties"):
        if not isinstance(document.get(key), list):
            errors.append(f"{key} must be a list")

    review = document.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
    elif review.get("status") not in REVIEW_STATUSES:
        errors.append("review.status must be pending, approved, or rejected")
    elif review.get("status") != "pending":
        for key in ("reviewed_by", "reviewed_at"):
            if not isinstance(review.get(key), str) or not review[key].strip():
                errors.append(
                    f"review.{key} must be non-empty after human review"
                )

    return errors, warnings


def validate_owner_input(
    document: Any,
    input_path: Path,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(document, dict):
        return ["cannot compare owner input with a non-object dossier"]
    owner_summary = document.get("owner")
    snapshot = document.get("input_snapshot")
    if not isinstance(owner_summary, dict) or not isinstance(snapshot, dict):
        return ["cannot compare owner input without owner and input_snapshot objects"]

    try:
        owner_document = json.loads(input_path.read_text(encoding="utf-8"))
        owners = owner_document.get("owners")
        if not isinstance(owners, list):
            raise ValueError("owner input has no owners list")
        person_id = owner_summary.get("person_id")
        if not isinstance(person_id, int) or isinstance(person_id, bool):
            raise ValueError("dossier owner.person_id must be an integer")
        source_owner = _find_owner(owners, person_id, None)
        actual = build_inventory(
            owner_document,
            source_owner,
            str(input_path),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"owner input comparison failed: {exc}"]

    source_path = snapshot.get("source_path")
    if isinstance(source_path, str):
        try:
            if Path(source_path).resolve() != input_path.resolve():
                errors.append(
                    "input_snapshot.source_path does not resolve to --owner-input"
                )
        except OSError as exc:
            errors.append(f"input_snapshot.source_path cannot be resolved: {exc}")

    expected = {
        "raw_blank_details": [
            item["field"] for item in actual["raw_blank_details"]
        ],
        "researchable_missing_details": actual["researchable_missing_details"],
        "optional_missing_details": actual["optional_missing_details"],
        "inapplicable_or_system_details": actual[
            "inapplicable_or_system_details"
        ],
        "existing_social_types": [
            item["type"] for item in actual["existing_socials"]
        ],
        "missing_priority_social_types": [
            item["type"] for item in actual["missing_priority_social_types"]
        ],
        "social_type_lookup": actual["social_type_lookup"],
    }
    for key, actual_value in expected.items():
        if snapshot.get(key) != actual_value:
            errors.append(f"input_snapshot.{key} does not match --owner-input")

    if owner_summary.get("display_name") != actual["owner"]["display_name"]:
        errors.append("owner.display_name does not match --owner-input")
    for index, proposal in enumerate(document.get("proposed_details", [])):
        if not isinstance(proposal, dict):
            continue
        if proposal.get("action") != "correct_existing":
            continue
        field = proposal.get("field")
        detail = source_owner.get("details", {}).get(field)
        current_value = detail.get("value") if isinstance(detail, dict) else detail
        if proposal.get("existing_value") != current_value:
            errors.append(
                f"proposed_details[{index}].existing_value does not match "
                "--owner-input"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an owner biography research dossier."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--owner-input",
        type=Path,
        help="Re-read the source owners document and verify the dossier snapshot.",
    )
    args = parser.parse_args()

    try:
        document = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Invalid dossier: {exc}", file=sys.stderr)
        return 1

    errors, warnings = validate(document)
    if args.owner_input is not None:
        errors.extend(validate_owner_input(document, args.owner_input))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Valid owner research dossier: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
