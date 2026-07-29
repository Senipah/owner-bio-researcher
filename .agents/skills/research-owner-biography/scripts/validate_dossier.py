from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from editorial_rules import (
    META_CAREER_OPENING_PATTERN,
    WORD_PATTERN as EDITORIAL_WORD_PATTERN,
    biography_pair_findings,
    editorial_findings,
)
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
    "not_applicable",
}
RECORD_TYPES = {"person", "institution", "unresolved_placeholder"}
EDITORIAL_DIMENSIONS = {
    "causal_clarity",
    "human_specificity",
    "durability",
    "source_invisibility",
    "natural_voice",
    "reader_orientation",
    "structural_independence",
}
CALIBRATION_ARCHETYPES = {
    "founder_operator",
    "acquirer_consolidator",
    "creative_industries",
    "inherited_operator",
    "heir_custodian",
    "royal_public_office",
    "investor_philanthropist",
    "sparse_public_record",
    "maritime_professional",
}
OPENING_MODES = {
    "present_identity",
    "defining_achievement",
    "decisive_event",
    "institution_or_asset",
    "formative_episode",
    "inherited_responsibility",
    "public_contribution",
}
NARRATIVE_SHAPES = {
    "identity_then_origin",
    "achievement_then_backstory",
    "decision_then_consequence",
    "institution_then_person",
    "formative_episode_then_payoff",
    "inheritance_then_stewardship",
    "core_work_deepened",
    "public_role_then_foundation",
}
FORBES_STATUSES = {"verified", "not_found", "ambiguous", "unavailable"}
REVIEW_STATUSES = {"pending", "approved", "rejected"}
INDUSTRIES = {
    "automotive": "Automotive",
    "construction_engineering": "Construction & Engineering",
    "cryptocurrency": "Cryptocurrency",
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
    "wealth_creation_industry": INDUSTRIES,
    "primary_industry": INDUSTRIES,
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
        "record_type",
        "owner",
        "input_snapshot",
        "research_status",
        "forbes_profile",
        "wealth_creation_industry",
        "primary_industry",
        "wealth_origin",
        "wealth_relationship",
        "biography",
        "long_biography",
        "biography_brief",
        "editorial_assessment",
        "editorial_note",
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

    if document.get("schema_version") != 7:
        errors.append("schema_version must be 7")
    record_type = document.get("record_type")
    if record_type not in RECORD_TYPES:
        errors.append("record_type is invalid")
    research_status = document.get("research_status")
    if research_status not in RESEARCH_STATUSES:
        errors.append("research_status is invalid")
    if record_type == "person" and research_status == "not_applicable":
        errors.append("person records cannot use research_status not_applicable")
    if (
        record_type == "person"
        and research_status in {"identity_conflict", "insufficient_evidence"}
    ):
        errors.append(
            "unresolved person identities must use "
            "record_type unresolved_placeholder"
        )
    if record_type == "institution" and research_status != "not_applicable":
        errors.append(
            "institution records must use research_status not_applicable"
        )
    if (
        record_type == "unresolved_placeholder"
        and research_status not in {"identity_conflict", "insufficient_evidence"}
    ):
        errors.append(
            "unresolved placeholders must use identity_conflict or "
            "insufficient_evidence"
        )

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
        if (
            record_type in {"institution", "unresolved_placeholder"}
            and isinstance(document.get(field), dict)
            and document[field].get("classification") != "unknown"
        ):
            errors.append(
                f"{field}.classification must be 'unknown' for "
                "non-person records"
            )

    biography_brief = document.get("biography_brief")
    editorial_assessment = document.get("editorial_assessment")
    editorial_note = document.get("editorial_note")
    if record_type == "person":
        if not isinstance(biography_brief, dict):
            errors.append("biography_brief must be an object for person records")
        else:
            for key in ("durable_identity", "defining_work"):
                value = biography_brief.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"biography_brief.{key} must be non-empty")
            for key in ("formative_context", "decisive_moment"):
                value = biography_brief.get(key)
                if (
                    value is not None
                    and (
                        not isinstance(value, str)
                        or not value.strip()
                    )
                ):
                    errors.append(
                        f"biography_brief.{key} must be null or non-empty"
                    )
            enduring_dimensions = biography_brief.get(
                "enduring_dimensions",
            )
            if (
                not isinstance(enduring_dimensions, list)
                or not 1 <= len(enduring_dimensions) <= 3
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in (
                        enduring_dimensions
                        if isinstance(enduring_dimensions, list)
                        else []
                    )
                )
            ):
                errors.append(
                    "biography_brief.enduring_dimensions must contain "
                    "1-3 non-empty strings"
                )
            character_detail = biography_brief.get("character_detail")
            if (
                character_detail is not None
                and (
                    not isinstance(character_detail, str)
                    or not character_detail.strip()
                )
            ):
                errors.append(
                    "biography_brief.character_detail must be null or non-empty"
                )
            opening_options = biography_brief.get("opening_options")
            option_modes: set[str] = set()
            if (
                not isinstance(opening_options, list)
                or len(opening_options) < 2
            ):
                errors.append(
                    "biography_brief.opening_options must contain at least "
                    "two options"
                )
            else:
                for index, option in enumerate(opening_options):
                    path = f"biography_brief.opening_options[{index}]"
                    if not isinstance(option, dict):
                        errors.append(f"{path} must be an object")
                        continue
                    mode = option.get("mode")
                    if mode not in OPENING_MODES:
                        errors.append(f"{path}.mode is invalid")
                    elif mode in option_modes:
                        errors.append(
                            "biography_brief.opening_options modes must be "
                            "distinct"
                        )
                    else:
                        option_modes.add(mode)
                    angle = option.get("angle")
                    if not isinstance(angle, str) or not angle.strip():
                        errors.append(f"{path}.angle must be non-empty")
                    elif META_CAREER_OPENING_PATTERN.search(angle):
                        errors.append(
                            f"{path}.angle uses abstract career-route "
                            "scaffolding"
                        )
            legacy_keys = {
                "wealth_or_prominence_route",
                "turning_point",
                "later_chapter",
            } & biography_brief.keys()
            if legacy_keys:
                errors.append(
                    "biography_brief contains legacy outline fields: "
                    f"{sorted(legacy_keys)}"
                )
            exclusions = biography_brief.get("excluded_transient_context")
            if not isinstance(exclusions, list) or any(
                not isinstance(item, str) or not item.strip()
                for item in (
                    exclusions if isinstance(exclusions, list) else []
                )
            ):
                errors.append(
                    "biography_brief.excluded_transient_context must be a "
                    "list of strings"
                )
            _source_ids(
                biography_brief.get("source_ids"),
                "biography_brief.source_ids",
                known_sources,
                errors,
            )
            brief_text = ". ".join(
                str(biography_brief.get(key) or "")
                for key in (
                    "durable_identity",
                    "defining_work",
                    "formative_context",
                    "decisive_moment",
                    "character_detail",
                )
            )
            if isinstance(enduring_dimensions, list):
                brief_text += ". " + ". ".join(
                    str(item) for item in enduring_dimensions
                )
            if isinstance(opening_options, list):
                brief_text += ". " + ". ".join(
                    str(option.get("angle") or "")
                    for option in opening_options
                    if isinstance(option, dict)
                )
            editorial_errors, editorial_warnings = editorial_findings(
                brief_text,
                section="biography_brief",
            )
            errors.extend(editorial_errors)
            warnings.extend(editorial_warnings)
        if not isinstance(editorial_assessment, dict):
            errors.append(
                "editorial_assessment must be an object for person records"
            )
        else:
            for dimension in EDITORIAL_DIMENSIONS:
                score = editorial_assessment.get(dimension)
                if (
                    not isinstance(score, int)
                    or isinstance(score, bool)
                    or not 4 <= score <= 5
                ):
                    errors.append(
                        f"editorial_assessment.{dimension} must be 4 or 5"
                    )
            archetypes = editorial_assessment.get(
                "calibration_archetypes",
            )
            if (
                not isinstance(archetypes, list)
                or not archetypes
                or any(
                    item not in CALIBRATION_ARCHETYPES
                    for item in (
                        archetypes if isinstance(archetypes, list) else []
                    )
                )
            ):
                errors.append(
                    "editorial_assessment.calibration_archetypes must be a "
                    "non-empty list of valid archetypes"
                )
            opening_mode = editorial_assessment.get("opening_mode")
            if opening_mode not in OPENING_MODES:
                errors.append("editorial_assessment.opening_mode is invalid")
            elif (
                isinstance(biography_brief, dict)
                and option_modes
                and opening_mode not in option_modes
            ):
                errors.append(
                    "editorial_assessment.opening_mode must select one of "
                    "biography_brief.opening_options"
                )
            if (
                editorial_assessment.get("narrative_shape")
                not in NARRATIVE_SHAPES
            ):
                errors.append(
                    "editorial_assessment.narrative_shape is invalid"
                )
            notes = editorial_assessment.get("notes")
            if not isinstance(notes, str) or not notes.strip():
                errors.append("editorial_assessment.notes must be non-empty")
        if editorial_note is not None:
            errors.append("editorial_note must be null for person records")
    else:
        if biography_brief is not None:
            errors.append("biography_brief must be null for non-person records")
        if editorial_assessment is not None:
            errors.append(
                "editorial_assessment must be null for non-person records"
            )
        if not isinstance(editorial_note, dict):
            errors.append("editorial_note must be an object for non-person records")
        else:
            note = editorial_note.get("plain_text")
            if not isinstance(note, str) or not note.strip():
                errors.append("editorial_note.plain_text must be non-empty")
            else:
                count = len(EDITORIAL_WORD_PATTERN.findall(note))
                if not 20 <= count <= 120:
                    errors.append("editorial_note must contain 20-120 words")
                if "\n" in note or "\r" in note:
                    errors.append("editorial_note.plain_text must be one paragraph")
            _confidence(
                editorial_note.get("confidence"),
                "editorial_note.confidence",
                errors,
            )
            _source_ids(
                editorial_note.get("source_ids"),
                "editorial_note.source_ids",
                known_sources,
                errors,
            )

    biography = document.get("biography")
    short_plain: str | None = None
    if record_type != "person":
        if biography is not None:
            errors.append("biography must be null for non-person records")
    elif not isinstance(biography, dict):
        errors.append("biography must be an object for person records")
    else:
        plain = biography.get("plain_text")
        if not isinstance(plain, str) or not plain.strip():
            errors.append("biography.plain_text must be non-empty")
        else:
            short_plain = plain
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
            editorial_errors, editorial_warnings = editorial_findings(
                plain,
                section="biography",
            )
            errors.extend(editorial_errors)
            warnings.extend(editorial_warnings)
        _confidence(biography.get("confidence"), "biography.confidence", errors)
        _source_ids(
            biography.get("source_ids"),
            "biography.source_ids",
            known_sources,
            errors,
        )

    long_biography = document.get("long_biography")
    long_plain_text: str | None = None
    if record_type != "person":
        if long_biography is not None:
            errors.append("long_biography must be null for non-person records")
    elif not isinstance(long_biography, dict):
        errors.append("long_biography must be an object for person records")
    else:
        long_plain = long_biography.get("plain_text")
        if not isinstance(long_plain, str) or not long_plain.strip():
            errors.append("long_biography.plain_text must be non-empty")
        else:
            long_plain_text = long_plain
            count = len(WORD_PATTERN.findall(long_plain))
            if long_biography.get("word_count") != count:
                errors.append(
                    f"long_biography.word_count must be {count}, not "
                    f"{long_biography.get('word_count')!r}"
                )
            if not 90 <= count <= 190:
                errors.append("long_biography must contain 90-190 words")
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
            editorial_errors, editorial_warnings = editorial_findings(
                long_plain,
                section="long_biography",
            )
            errors.extend(editorial_errors)
            warnings.extend(editorial_warnings)
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

    if short_plain is not None and long_plain_text is not None:
        display_name = (
            str(owner.get("display_name") or "")
            if isinstance(owner, dict)
            else ""
        )
        pair_errors, pair_warnings, _ = biography_pair_findings(
            short_plain,
            long_plain_text,
            display_name=display_name,
        )
        errors.extend(pair_errors)
        warnings.extend(pair_warnings)
        if (
            (pair_errors or pair_warnings)
            and isinstance(editorial_assessment, dict)
            and editorial_assessment.get("structural_independence") == 5
        ):
            errors.append(
                "editorial_assessment.structural_independence cannot be 5 "
                "while the biography-pair audit reports overlap"
            )

    for collection in ("proposed_details", "proposed_socials"):
        items = document.get(collection)
        if not isinstance(items, list):
            errors.append(f"{collection} must be a list")
            continue
        if record_type != "person" and items:
            errors.append(f"{collection} must be empty for non-person records")
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


def _current_vessel_names(owner: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    ownership = owner.get("vessel_ownership")
    if isinstance(ownership, dict):
        for key in ("relationships", "current_vessels"):
            for relationship in ownership.get(key, []):
                if (
                    isinstance(relationship, dict)
                    and relationship.get("is_current")
                    and isinstance(relationship.get("vessel_name"), str)
                ):
                    names.add(relationship["vessel_name"].strip())
        largest = ownership.get("largest_known_current_vessel")
        if (
            isinstance(largest, dict)
            and isinstance(largest.get("vessel_name"), str)
        ):
            names.add(largest["vessel_name"].strip())
    for relationship in owner.get("top_100", {}).get("relationships", []):
        if (
            isinstance(relationship, dict)
            and relationship.get("is_current")
            and isinstance(relationship.get("vessel_name"), str)
        ):
            names.add(relationship["vessel_name"].strip())
    return {name for name in names if name}


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
    if document.get("record_type") == "person":
        biography_text = " ".join(
            value.get("plain_text", "")
            for value in (
                document.get("biography"),
                document.get("long_biography"),
            )
            if isinstance(value, dict)
        ).casefold()
        for vessel_name in sorted(_current_vessel_names(source_owner)):
            vessel_pattern = re.compile(
                rf"(?<!\w){re.escape(vessel_name.casefold())}(?!\w)"
            )
            if len(vessel_name) >= 3 and vessel_pattern.search(biography_text):
                errors.append(
                    "biographies mention current vessel name "
                    f"{vessel_name!r}; current ownership is ranking context only"
                )
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
    parser.add_argument(
        "--strict-editorial",
        action="store_true",
        help="Treat editorial warnings as validation errors.",
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
    if args.strict_editorial and warnings:
        errors.extend(f"strict editorial: {warning}" for warning in warnings)
        warnings = []
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
