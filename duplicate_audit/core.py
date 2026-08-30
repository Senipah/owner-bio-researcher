from __future__ import annotations

import hashlib
import html
import itertools
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


AUDIT_DATASET = "owner_duplicate_audit"
CANDIDATE_DATASET = "owner_duplicate_candidates"

JUDGMENT_CLASSIFICATIONS = frozenset(
    {
        "probable_duplicate",
        "possible_duplicate",
        "probably_distinct",
        "insufficient_evidence",
    }
)
FINAL_CLASSIFICATIONS = JUDGMENT_CLASSIFICATIONS | {"needs_manual_review"}

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_ALIAS_SPLIT_RE = re.compile(r"\s*(?:,|;|/|\||\n|\r)+\s*")

_DETAIL_KEYS = (
    "title",
    "first_name",
    "middle_names",
    "last_name",
    "name_suffix",
    "display_name",
    "sort_first_name",
    "sort_last_name",
    "sort_name",
    "unknown_name",
    "gender",
    "birth_day",
    "birth_month",
    "birth_year",
    "birth_country",
    "place_of_birth",
    "nationality",
    "secondary_nationality",
    "main_residence_country",
    "secondary_residence_country",
    "death_day",
    "death_month",
    "death_year",
    "mortality_status",
    "known_for_title",
)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plain(value: Any, *, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = html.unescape(_TAG_RE.sub(" ", str(value)))
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:limit]


def _detail_value(owner: Mapping[str, Any], key: str) -> str:
    details = owner.get("details")
    if not isinstance(details, Mapping):
        return ""
    entry = details.get(key)
    if not isinstance(entry, Mapping):
        return ""
    return _plain(entry.get("value"))


def _employer_names(report: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    employers = report.get("employers")
    if isinstance(employers, list):
        for employer in employers:
            if isinstance(employer, Mapping):
                for key in ("name", "company", "title"):
                    value = _plain(employer.get(key))
                    if value:
                        result.append(value)
                        break
            else:
                value = _plain(employer)
                if value:
                    result.append(value)
    display = _plain(report.get("employer_display"))
    if display:
        result.append(display)
    return list(dict.fromkeys(result))


def _aliases(report: Mapping[str, Any]) -> list[str]:
    raw = _plain(report.get("akas"))
    if not raw:
        return []
    return list(
        dict.fromkeys(part for part in _ALIAS_SPLIT_RE.split(raw) if part.strip())
    )


def _vessel_names(owner: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    top_100 = owner.get("top_100")
    if isinstance(top_100, Mapping):
        relationships = top_100.get("relationships")
        if isinstance(relationships, list):
            for relationship in relationships:
                if isinstance(relationship, Mapping):
                    value = _plain(relationship.get("vessel_name"))
                    if value:
                        names.append(value)

    vessel_ownership = owner.get("vessel_ownership")
    if isinstance(vessel_ownership, Mapping):
        for key in ("relationships", "vessels"):
            relationships = vessel_ownership.get(key)
            if not isinstance(relationships, list):
                continue
            for relationship in relationships:
                if not isinstance(relationship, Mapping):
                    continue
                value = _plain(
                    relationship.get("vessel_name") or relationship.get("name")
                )
                if value:
                    names.append(value)
    return list(dict.fromkeys(names))


def build_identity_card(owner: Mapping[str, Any]) -> dict[str, Any]:
    """Return the allow-listed identity evidence used by the audit.

    Biographies, internal notes, baselines, and workflow state are intentionally
    absent. This object is safe to use as the hosted-model input boundary.
    """

    report_value = owner.get("report")
    report = report_value if isinstance(report_value, Mapping) else {}
    details = {
        key: value
        for key in _DETAIL_KEYS
        if (value := _detail_value(owner, key))
    }

    report_first = _plain(report.get("first_name"))
    report_last = _plain(report.get("last_name"))
    detail_name_parts = [
        details.get("title", ""),
        details.get("first_name", ""),
        details.get("middle_names", ""),
        details.get("last_name", ""),
        details.get("name_suffix", ""),
    ]
    full_name = _SPACE_RE.sub(
        " ", " ".join(part for part in detail_name_parts if part)
    ).strip()
    if not full_name:
        full_name = f"{report_first} {report_last}".strip()
    if not full_name:
        full_name = details.get("display_name", "") or "Unknown owner"

    socials: list[dict[str, str]] = []
    raw_socials = owner.get("social_media_profiles")
    if isinstance(raw_socials, list):
        for profile in raw_socials:
            if not isinstance(profile, Mapping):
                continue
            url = _plain(profile.get("url"), limit=1000)
            if not url:
                continue
            socials.append(
                {
                    "type": _plain(profile.get("type"), limit=100),
                    "url": url,
                }
            )

    return {
        "person_id": int(owner["person_id"]),
        "profile_url": _plain(owner.get("profile_url"), limit=1000),
        "image_url": _plain(report.get("image_url"), limit=1000),
        "full_name": full_name,
        "report_names": {
            "first_name": report_first,
            "last_name": report_last,
        },
        "aliases": _aliases(report),
        "details": details,
        "known_for": _plain(report.get("known_for")),
        "employers": _employer_names(report),
        "report_nationality": _plain(report.get("nationality")),
        "social_profiles": socials,
        "vessels": _vessel_names(owner),
        "enrichment_status": _plain(
            (owner.get("enrichment") or {}).get("status")
            if isinstance(owner.get("enrichment"), Mapping)
            else ""
        ),
    }


def embedding_views(card: Mapping[str, Any]) -> dict[str, str]:
    details_value = card.get("details")
    details = details_value if isinstance(details_value, Mapping) else {}
    report_names_value = card.get("report_names")
    report_names = (
        report_names_value if isinstance(report_names_value, Mapping) else {}
    )

    name_lines = [
        f"Full name: {_plain(card.get('full_name'))}",
        f"Report first name: {_plain(report_names.get('first_name'))}",
        f"Report last name: {_plain(report_names.get('last_name'))}",
    ]
    for key in (
        "display_name",
        "first_name",
        "middle_names",
        "last_name",
        "sort_name",
        "sort_first_name",
        "sort_last_name",
    ):
        value = _plain(details.get(key))
        if value:
            name_lines.append(f"{key.replace('_', ' ')}: {value}")
    aliases = [_plain(value) for value in card.get("aliases", []) if _plain(value)]
    if aliases:
        name_lines.append("Known aliases: " + "; ".join(aliases))

    identity_lines = list(name_lines)
    employers = [
        _plain(value) for value in card.get("employers", []) if _plain(value)
    ]
    if employers:
        identity_lines.append("Employers: " + "; ".join(employers))
    known_for = _plain(card.get("known_for")) or _plain(details.get("known_for_title"))
    if known_for:
        identity_lines.append(f"Known for: {known_for}")
    for key in (
        "gender",
        "birth_day",
        "birth_month",
        "birth_year",
        "birth_country",
        "place_of_birth",
        "nationality",
        "secondary_nationality",
        "main_residence_country",
        "secondary_residence_country",
        "death_year",
        "mortality_status",
    ):
        value = _plain(details.get(key))
        if value:
            identity_lines.append(f"{key.replace('_', ' ')}: {value}")
    report_nationality = _plain(card.get("report_nationality"))
    if report_nationality:
        identity_lines.append(f"Report nationality: {report_nationality}")
    vessels = [_plain(value) for value in card.get("vessels", []) if _plain(value)]
    if vessels:
        identity_lines.append("Known vessels: " + "; ".join(vessels))
    social_profiles = card.get("social_profiles")
    if isinstance(social_profiles, list):
        social_hosts = sorted(
            {
                urlsplit(_plain(item.get("url"))).netloc.casefold()
                for item in social_profiles
                if isinstance(item, Mapping) and _plain(item.get("url"))
            }
        )
        if social_hosts:
            identity_lines.append("Social profile hosts: " + "; ".join(social_hosts))

    return {
        "name": "\n".join(line for line in name_lines if line.strip()),
        "identity": "\n".join(line for line in identity_lines if line.strip()),
    }


def normalize_identity_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _plain(value).casefold())
    return "".join(character for character in text if character.isalnum())


def normalize_url(value: Any) -> str:
    raw = _plain(value, limit=2000)
    if not raw:
        return ""
    candidate = raw if "://" in raw else f"https://{raw}"
    parsed = urlsplit(candidate)
    host = parsed.netloc.casefold().removeprefix("www.")
    path = parsed.path.rstrip("/")
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.casefold().startswith("utm_")
        )
    )
    return urlunsplit(("", host, path, query, "")).lstrip("//")


def _full_birth_date(card: Mapping[str, Any]) -> str:
    details = card.get("details")
    if not isinstance(details, Mapping):
        return ""
    parts = [
        normalize_identity_text(details.get("birth_year")),
        normalize_identity_text(details.get("birth_month")),
        normalize_identity_text(details.get("birth_day")),
    ]
    return "-".join(parts) if all(parts) else ""


def _all_normalized_names(card: Mapping[str, Any]) -> set[str]:
    names = {normalize_identity_text(card.get("full_name"))}
    details = card.get("details")
    if isinstance(details, Mapping):
        for key in ("display_name", "sort_name"):
            names.add(normalize_identity_text(details.get(key)))
    aliases = card.get("aliases")
    if isinstance(aliases, list):
        names.update(normalize_identity_text(value) for value in aliases)
    return {value for value in names if value}


def _social_urls(card: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    profiles = card.get("social_profiles")
    if isinstance(profiles, list):
        for profile in profiles:
            if isinstance(profile, Mapping):
                value = normalize_url(profile.get("url"))
                if value:
                    result.add(value)
    return result


def pair_signals(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    left_names = _all_normalized_names(left)
    right_names = _all_normalized_names(right)
    shared_names = sorted(left_names & right_names)
    if shared_names:
        signals.append(
            {
                "type": "shared_normalized_name",
                "description": "A full, display, sort, or alias name matches after normalization.",
            }
        )

    if (
        normalize_identity_text(left.get("full_name"))
        in {
            normalize_identity_text(value)
            for value in right.get("aliases", [])
        }
        or normalize_identity_text(right.get("full_name"))
        in {
            normalize_identity_text(value)
            for value in left.get("aliases", [])
        }
    ):
        signals.append(
            {
                "type": "name_alias_cross_match",
                "description": "One record's primary name appears among the other's aliases.",
            }
        )

    shared_socials = sorted(_social_urls(left) & _social_urls(right))
    if shared_socials:
        signals.append(
            {
                "type": "shared_social_url",
                "description": "The records share at least one normalized social-profile URL.",
            }
        )

    left_birth = _full_birth_date(left)
    right_birth = _full_birth_date(right)
    if left_birth and left_birth == right_birth:
        signals.append(
            {
                "type": "shared_full_birth_date",
                "description": "The records contain the same complete birth date.",
            }
        )

    left_image = normalize_url(left.get("image_url"))
    right_image = normalize_url(right.get("image_url"))
    if left_image and left_image == right_image:
        signals.append(
            {
                "type": "shared_image_url",
                "description": "The records reference the same profile-image URL.",
            }
        )

    left_employers = {
        normalize_identity_text(value) for value in left.get("employers", [])
    }
    right_employers = {
        normalize_identity_text(value) for value in right.get("employers", [])
    }
    if {value for value in left_employers if value} & {
        value for value in right_employers if value
    }:
        signals.append(
            {
                "type": "shared_employer",
                "description": "The records share an employer name after normalization.",
            }
        )
    return signals


def _record_pair(
    pairs: dict[tuple[int, int], dict[str, Any]],
    left_id: int,
    right_id: int,
    *,
    view: str | None = None,
    score: float | None = None,
) -> None:
    if left_id == right_id:
        return
    key = tuple(sorted((int(left_id), int(right_id))))
    item = pairs.setdefault(
        key,
        {
            "candidate_id": f"pair_{key[0]}_{key[1]}",
            "person_ids": list(key),
            "retrieval": {"embedding_scores": {}, "signals": []},
        },
    )
    if view is not None and score is not None:
        previous = item["retrieval"]["embedding_scores"].get(view)
        if previous is None or score > previous:
            item["retrieval"]["embedding_scores"][view] = round(float(score), 6)


def _strong_signal_pairs(cards: Sequence[Mapping[str, Any]]) -> set[tuple[int, int]]:
    buckets: dict[tuple[str, str], list[int]] = defaultdict(list)
    for card in cards:
        person_id = int(card["person_id"])
        primary_name = normalize_identity_text(card.get("full_name"))
        if primary_name:
            buckets[("name", primary_name)].append(person_id)
        for social in _social_urls(card):
            buckets[("social", social)].append(person_id)
        birth_date = _full_birth_date(card)
        details = card.get("details")
        last_name = ""
        if isinstance(details, Mapping):
            last_name = normalize_identity_text(details.get("last_name"))
        if not last_name:
            report_names = card.get("report_names")
            if isinstance(report_names, Mapping):
                last_name = normalize_identity_text(report_names.get("last_name"))
        if birth_date and last_name:
            buckets[("birth_surname", f"{birth_date}:{last_name}")].append(person_id)
        image_url = normalize_url(card.get("image_url"))
        if image_url:
            buckets[("image", image_url)].append(person_id)

    result: set[tuple[int, int]] = set()
    for (kind, _), values in buckets.items():
        unique_ids = sorted(set(values))
        maximum_bucket = 20 if kind in {"name", "social", "birth_surname"} else 5
        if 2 <= len(unique_ids) <= maximum_bucket:
            result.update(itertools.combinations(unique_ids, 2))
    return result


def discover_candidates(
    cards: Sequence[Mapping[str, Any]],
    embeddings_by_view: Mapping[str, Sequence[Sequence[float]]],
    *,
    thresholds: Mapping[str, float],
    top_k: int = 8,
    chunk_size: int = 256,
) -> list[dict[str, Any]]:
    """Use AI embedding neighbours plus high-recall evidence links.

    Deterministic signals may place a pair in the review set, but never decide
    whether it is a duplicate. The later model judgment owns that decision.
    """

    if not cards:
        return []
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised by CLI environment
        raise RuntimeError(
            "Duplicate candidate discovery requires numpy. Install "
            "duplicate_audit/requirements.txt into the repository venv."
        ) from exc

    person_ids = [int(card["person_id"]) for card in cards]
    if len(person_ids) != len(set(person_ids)):
        raise ValueError("Identity cards contain duplicate person IDs")

    pairs: dict[tuple[int, int], dict[str, Any]] = {}
    count = len(cards)
    neighbour_count = min(top_k, max(0, count - 1))
    for view, vectors in embeddings_by_view.items():
        if view not in thresholds:
            raise ValueError(f"No similarity threshold configured for {view!r}")
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != count:
            raise ValueError(
                f"Embedding view {view!r} has shape {matrix.shape}; "
                f"expected ({count}, dimensions)"
            )
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError(f"Embedding view {view!r} contains a zero vector")
        normalized = matrix / norms
        if neighbour_count == 0:
            continue

        for start in range(0, count, chunk_size):
            stop = min(count, start + chunk_size)
            similarities = normalized[start:stop] @ normalized.T
            for offset, row in enumerate(similarities):
                source_index = start + offset
                row[source_index] = -np.inf
                selected = np.argpartition(row, -neighbour_count)[-neighbour_count:]
                selected = selected[np.argsort(row[selected])[::-1]]
                for target_index in selected.tolist():
                    score = float(row[target_index])
                    if score < float(thresholds[view]):
                        continue
                    _record_pair(
                        pairs,
                        person_ids[source_index],
                        person_ids[target_index],
                        view=view,
                        score=score,
                    )

    for left_id, right_id in _strong_signal_pairs(cards):
        _record_pair(pairs, left_id, right_id)

    cards_by_id = {int(card["person_id"]): card for card in cards}
    result = list(pairs.values())
    for candidate in result:
        left_id, right_id = candidate["person_ids"]
        candidate["retrieval"]["signals"] = pair_signals(
            cards_by_id[left_id], cards_by_id[right_id]
        )
        scores = candidate["retrieval"]["embedding_scores"].values()
        candidate["retrieval"]["maximum_embedding_score"] = (
            round(max(scores), 6) if scores else None
        )

    signal_weights = {
        "shared_social_url": 5,
        "shared_full_birth_date": 4,
        "name_alias_cross_match": 3,
        "shared_normalized_name": 2,
        "shared_image_url": 2,
        "shared_employer": 1,
    }

    def sort_key(item: Mapping[str, Any]) -> tuple[float, float, str]:
        retrieval = item["retrieval"]
        signal_score = sum(
            signal_weights.get(signal.get("type", ""), 0)
            for signal in retrieval.get("signals", [])
        )
        embedding_score = retrieval.get("maximum_embedding_score") or 0.0
        return (-float(signal_score), -float(embedding_score), item["candidate_id"])

    result.sort(key=sort_key)
    return result


def judgment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": sorted(JUDGMENT_CLASSIFICATIONS),
            },
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            "summary": {"type": "string"},
            "evidence_for": {"type": "array", "items": {"type": "string"}},
            "evidence_against": {
                "type": "array",
                "items": {"type": "string"},
            },
            "missing_evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
            "more_complete_person_id": {
                "type": ["integer", "null"],
            },
            "completeness_reason": {"type": "string"},
        },
        "required": [
            "classification",
            "confidence",
            "summary",
            "evidence_for",
            "evidence_against",
            "missing_evidence",
            "more_complete_person_id",
            "completeness_reason",
        ],
        "additionalProperties": False,
    }


def validate_judgment(
    judgment: Mapping[str, Any], *, person_ids: Iterable[int]
) -> dict[str, Any]:
    classification = judgment.get("classification")
    if classification not in JUDGMENT_CLASSIFICATIONS:
        raise ValueError(f"Invalid duplicate classification: {classification!r}")
    confidence = judgment.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int):
        raise ValueError("Judgment confidence must be an integer")
    if not 0 <= confidence <= 100:
        raise ValueError("Judgment confidence must be between 0 and 100")

    allowed_ids = {int(value) for value in person_ids}
    more_complete = judgment.get("more_complete_person_id")
    if more_complete is not None and more_complete not in allowed_ids:
        raise ValueError(
            "more_complete_person_id must be null or one of the candidate records"
        )
    for key in ("evidence_for", "evidence_against", "missing_evidence"):
        if not isinstance(judgment.get(key), list) or any(
            not isinstance(item, str) for item in judgment[key]
        ):
            raise ValueError(f"Judgment {key} must be an array of strings")
    for key in ("summary", "completeness_reason"):
        if not isinstance(judgment.get(key), str):
            raise ValueError(f"Judgment {key} must be a string")
    return dict(judgment)


def resolve_final_classification(
    primary: Mapping[str, Any], verifier: Mapping[str, Any] | None
) -> str:
    primary_class = primary.get("classification")
    if primary_class not in JUDGMENT_CLASSIFICATIONS:
        raise ValueError(f"Invalid primary classification: {primary_class!r}")
    if primary_class != "probable_duplicate":
        return str(primary_class)
    if verifier is None:
        return "needs_manual_review"

    verifier_class = verifier.get("classification")
    if verifier_class not in JUDGMENT_CLASSIFICATIONS:
        raise ValueError(f"Invalid verifier classification: {verifier_class!r}")
    if verifier_class == "probable_duplicate":
        return "probable_duplicate"
    if verifier_class == "possible_duplicate":
        return "possible_duplicate"
    return "needs_manual_review"


def prompt_card(card: Mapping[str, Any]) -> dict[str, Any]:
    """Strip local navigation and image locations from the hosted text prompt."""

    allowed = {
        key: card.get(key)
        for key in (
            "person_id",
            "full_name",
            "report_names",
            "aliases",
            "details",
            "known_for",
            "employers",
            "report_nationality",
            "social_profiles",
            "vessels",
            "enrichment_status",
        )
    }
    return json.loads(json.dumps(allowed, ensure_ascii=False))


def connected_candidate_clusters(
    candidates: Sequence[Mapping[str, Any]],
    *,
    included_classifications: set[str] | None = None,
) -> list[list[int]]:
    included = included_classifications or {
        "probable_duplicate",
        "possible_duplicate",
        "needs_manual_review",
    }
    adjacency: dict[int, set[int]] = defaultdict(set)
    for candidate in candidates:
        if candidate.get("final_classification") not in included:
            continue
        left_id, right_id = (int(value) for value in candidate["person_ids"])
        adjacency[left_id].add(right_id)
        adjacency[right_id].add(left_id)

    clusters: list[list[int]] = []
    seen: set[int] = set()
    for root in sorted(adjacency):
        if root in seen:
            continue
        stack = [root]
        cluster: list[int] = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            cluster.append(current)
            stack.extend(sorted(adjacency[current] - seen, reverse=True))
        clusters.append(sorted(cluster))
    return clusters
