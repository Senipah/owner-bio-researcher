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
WEALTH_CLASSES = {
    "self_made_operating_business",
    "self_made_finance_investment",
    "inherited",
    "inherited_and_expanded",
    "family_business",
    "privatization_or_state_assets",
    "natural_resources",
    "real_estate",
    "entertainment_or_sport",
    "mixed",
    "unclear",
}


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
        "wealth_origin",
        "biography",
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

    if document.get("schema_version") != 2:
        errors.append("schema_version must be 2")
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

    wealth = document.get("wealth_origin")
    if not isinstance(wealth, dict):
        errors.append("wealth_origin must be an object")
    else:
        if wealth.get("classification") not in WEALTH_CLASSES:
            errors.append("wealth_origin.classification is invalid")
        if not isinstance(wealth.get("summary"), str) or not wealth["summary"].strip():
            errors.append("wealth_origin.summary must be non-empty")
        _confidence(wealth.get("confidence"), "wealth_origin.confidence", errors)
        _source_ids(
            wealth.get("source_ids"),
            "wealth_origin.source_ids",
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
            words = re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", plain)
            count = len(words)
            if biography.get("word_count") != count:
                errors.append(
                    f"biography.word_count must be {count}, not "
                    f"{biography.get('word_count')!r}"
                )
            if not 45 <= count <= 110:
                errors.append("biography must contain 45-110 words")
            elif not 55 <= count <= 90:
                warnings.append("biography is outside the preferred 55-90 words")
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
