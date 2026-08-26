from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from editorial_rules import (
    FORMULAIC_SECOND_PARAGRAPH_PATTERN,
    ORIGIN_STORY_OPENING_PATTERN,
    STOCK_PHRASES,
    SYNTHETIC_ENDING_PATTERN,
    WORD_PATTERN,
    biography_pair_findings,
    editorial_findings,
    final_sentence,
    paragraphs,
)


BIRTH_LED_PATTERN = re.compile(
    r"^(?:Born\b|[^.!?]{0,90}\bwas born\b)",
    re.IGNORECASE,
)


def _load_people(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    people: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.research.json")):
        try:
            dossier = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: cannot read dossier: {exc}")
            continue
        if dossier.get("schema_version") != 8:
            problems.append(f"{path.name}: schema_version is not 8")
            continue
        if dossier.get("record_type") != "person":
            continue
        short = dossier.get("biography")
        long = dossier.get("long_biography")
        if not isinstance(short, dict) or not isinstance(long, dict):
            problems.append(f"{path.name}: person dossier has no biographies")
            continue
        classifications = {}
        for field in (
            "wealth_creation_industry",
            "primary_industry",
            "wealth_origin",
            "wealth_relationship",
        ):
            value = dossier.get(field)
            classification = (
                value.get("classification")
                if isinstance(value, dict)
                else None
            )
            if not isinstance(classification, str) or not classification:
                problems.append(
                    f"{path.name}: {field}.classification is missing"
                )
                classification = None
            classifications[field] = classification
        assessment = dossier.get("editorial_assessment")
        if not isinstance(assessment, dict):
            assessment = {}
        for field in ("opening_mode", "narrative_shape"):
            if not isinstance(assessment.get(field), str):
                problems.append(
                    f"{path.name}: editorial_assessment.{field} is missing"
                )
        people.append(
            {
                "path": path,
                "name": dossier.get("owner", {}).get(
                    "display_name",
                    path.stem,
                ),
                "short": short.get("plain_text", ""),
                "long": long.get("plain_text", ""),
                **classifications,
                "opening_mode": assessment.get("opening_mode"),
                "narrative_shape": assessment.get("narrative_shape"),
            }
        )
    return people, problems


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in WORD_PATTERN.findall(text)]


def _repeated_ngrams(
    people: list[dict[str, Any]],
    *,
    size: int,
    minimum_owners: int,
) -> list[tuple[str, list[str]]]:
    owners_by_gram: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for person in people:
        tokens = _tokens(f"{person['short']} {person['long']}")
        for index in range(len(tokens) - size + 1):
            gram = tuple(tokens[index:index + size])
            if any(any(character.isdigit() for character in token) for token in gram):
                continue
            owners_by_gram[gram].add(str(person["name"]))
    repeated = [
        (" ".join(gram), sorted(owners))
        for gram, owners in owners_by_gram.items()
        if len(owners) >= minimum_owners
    ]
    repeated.sort(key=lambda item: (-len(item[1]), item[0]))
    return repeated


def _business_people(
    people: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        person
        for person in people
        if person.get("wealth_origin") != "dynastic_royal"
        and (
            person.get("primary_industry") not in {None, "unknown"}
            or person.get("wealth_relationship")
            not in {None, "unknown", "royal_beneficiary"}
        )
    ]


def _ratio_limit(count: int) -> float:
    return 0.5 if count < 10 else 0.35


def _ratio_issue(
    *,
    label: str,
    owners: list[str],
    cohort_size: int,
) -> str | None:
    if cohort_size < 5:
        return None
    ratio = len(owners) / cohort_size
    if ratio <= _ratio_limit(cohort_size):
        return None
    return (
        f"{len(owners)}/{cohort_size} business profiles use {label}: "
        f"{', '.join(sorted(owners))}"
    )


def audit(
    directory: Path,
    *,
    minimum_owners: int = 3,
) -> tuple[list[str], list[str], int]:
    people, issues = _load_people(directory)
    observations: list[str] = []
    if not people:
        issues.append("no schema-v8 person dossiers found")
        return issues, observations, 0
    repetition_threshold = max(
        minimum_owners,
        math.ceil(len(people) * 0.08),
    )
    pair_rankings: list[tuple[float, int, float, str]] = []

    for person in people:
        for section in ("short", "long"):
            errors, warnings = editorial_findings(
                str(person[section]),
                section=(
                    "biography"
                    if section == "short"
                    else "long_biography"
                ),
            )
            issues.extend(
                f"{person['name']} {section}: {finding}"
                for finding in errors + warnings
            )
        pair_errors, pair_warnings, pair_metrics = biography_pair_findings(
            str(person["short"]),
            str(person["long"]),
            display_name=str(person["name"]),
        )
        issues.extend(
            f"{person['name']} pair: {finding}"
            for finding in pair_errors + pair_warnings
        )
        pair_rankings.append(
            (
                float(pair_metrics["content_containment"]),
                int(pair_metrics["shared_trigrams"]),
                float(pair_metrics["max_sentence_similarity"]),
                str(person["name"]),
            )
        )

    for containment, trigrams, sentence_similarity, name in sorted(
        pair_rankings,
        reverse=True,
    )[:5]:
        observations.append(
            f"short-long overlap for {name}: "
            f"{containment:.0%} short-content containment, "
            f"{trigrams} shared three-word phrases, "
            f"{sentence_similarity:.0%} maximum sentence similarity"
        )

    combined_by_owner = {
        str(person["name"]): (
            f"{person['short']} {person['long']}".casefold()
        )
        for person in people
    }
    for phrase in STOCK_PHRASES:
        owners = sorted(
            name
            for name, text in combined_by_owner.items()
            if phrase in text
        )
        if len(owners) >= repetition_threshold:
            issues.append(
                f"stock phrase {phrase!r} appears for {len(owners)} owners: "
                f"{', '.join(owners)}"
            )

    birth_led = [
        str(person["name"])
        for person in people
        if BIRTH_LED_PATTERN.search(str(person["long"]))
    ]
    if len(people) >= 5 and len(birth_led) / len(people) > 0.5:
        issues.append(
            f"{len(birth_led)}/{len(people)} long biographies are birth-led: "
            f"{', '.join(sorted(birth_led))}"
        )

    business_people = _business_people(people)
    origin_led = [
        str(person["name"])
        for person in business_people
        if ORIGIN_STORY_OPENING_PATTERN.search(
            paragraphs(str(person["long"]))[0],
        )
    ]
    formulaic_second_paragraph = [
        str(person["name"])
        for person in business_people
        if len(paragraphs(str(person["long"]))) > 1
        and FORMULAIC_SECOND_PARAGRAPH_PATTERN.search(
            paragraphs(str(person["long"]))[1],
        )
    ]
    synthetic_endings = [
        str(person["name"])
        for person in business_people
        if SYNTHETIC_ENDING_PATTERN.search(
            final_sentence(str(person["long"])),
        )
    ]
    for label, owners in (
        ("origin-story openings", origin_led),
        ("formulaic paragraph-two transitions", formulaic_second_paragraph),
        ("synthetic tie-back conclusions", synthetic_endings),
    ):
        issue = _ratio_issue(
            label=label,
            owners=owners,
            cohort_size=len(business_people),
        )
        if issue:
            issues.append(issue)

    for field, label in (
        ("opening_mode", "declared opening mode"),
        ("narrative_shape", "declared narrative shape"),
    ):
        values: dict[str, list[str]] = defaultdict(list)
        for person in business_people:
            value = person.get(field)
            if isinstance(value, str) and value:
                values[value].append(str(person["name"]))
        if values:
            dominant_value, owners = max(
                values.items(),
                key=lambda item: len(item[1]),
            )
            issue = _ratio_issue(
                label=f"{label} {dominant_value!r}",
                owners=owners,
                cohort_size=len(business_people),
            )
            if issue:
                issues.append(issue)

    opening_counts: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for person in people:
        opening = tuple(_tokens(str(person["long"]))[:6])
        if opening:
            opening_counts[opening].append(str(person["name"]))
    for opening, owners in opening_counts.items():
        if len(owners) >= repetition_threshold:
            issues.append(
                f"shared long-biography opening {' '.join(opening)!r}: "
                f"{', '.join(sorted(owners))}"
            )

    for gram, owners in _repeated_ngrams(
        people,
        size=4,
        minimum_owners=minimum_owners,
    )[:20]:
        observations.append(
            f"repeated four-word phrase {gram!r} appears for "
            f"{len(owners)} owners"
        )

    return issues, observations, len(people)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a dossier tranche for repeated editorial patterns."
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--minimum-owners",
        type=int,
        default=3,
        help="Minimum distinct owners for a repeated pattern (default: 3).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when editorial issues are found.",
    )
    args = parser.parse_args()
    if args.minimum_owners < 2:
        print("--minimum-owners must be at least 2", file=sys.stderr)
        return 1

    issues, observations, count = audit(
        args.directory,
        minimum_owners=args.minimum_owners,
    )
    print(f"Audited {count} schema-v8 person dossiers.")
    for observation in observations:
        print(f"INFO: {observation}")
    for issue in issues:
        print(f"ISSUE: {issue}", file=sys.stderr)
    if issues and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
