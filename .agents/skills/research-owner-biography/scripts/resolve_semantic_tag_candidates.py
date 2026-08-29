from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json
from src.tags import (
    DEFAULT_TAG_CATALOGUE_PATH,
    TagCatalogue,
    TagResolutionError,
    normalize_tag_name,
)


def _load_addition_module() -> Any:
    path = SCRIPT_DIR / "add_catalogue_tag.py"
    specification = importlib.util.spec_from_file_location(
        "semantic_review_add_catalogue_tag", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


ADD_TAG = _load_addition_module()
DEFAULT_REVIEW_DIR = (
    REPO_ROOT / "output" / "owner-research" / "tag-semantic-review" / "reviews"
)
DEFAULT_AUDIT_DIR = REPO_ROOT / "output" / "owner-research" / "tag-semantic-review"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = normalize_tag_name(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(value.strip())
    return result


def _candidate_groups(
    reviews: list[tuple[Path, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for review_path, review in reviews:
        candidates = review.get("catalogue_candidates")
        if not isinstance(candidates, list):
            raise ValueError(f"{review_path}: catalogue_candidates must be a list")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError(f"{review_path}: candidate must be an object")
            name = candidate.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"{review_path}: candidate name must be non-empty")
            key = normalize_tag_name(name)
            group = groups.setdefault(
                key,
                {
                    "candidate_names": [],
                    "aliases": [],
                    "facets": [],
                    "proposals": [],
                },
            )
            group["candidate_names"].append(name.strip())
            aliases = candidate.get("aliases")
            facets = candidate.get("facets")
            if not isinstance(aliases, list) or any(
                not isinstance(value, str) for value in aliases
            ):
                raise ValueError(f"{review_path}: {name} aliases must be strings")
            if not isinstance(facets, list) or any(
                not isinstance(value, str) for value in facets
            ):
                raise ValueError(f"{review_path}: {name} facets must be strings")
            group["aliases"].extend(aliases)
            group["facets"].extend(facets)
            group["proposals"].append(
                {
                    "review_path": review_path,
                    "review": review,
                    "candidate": candidate,
                }
            )
    for group in groups.values():
        group["candidate_names"] = _unique(group["candidate_names"])
        group["aliases"] = _unique(group["aliases"])
        group["facets"] = sorted(set(group["facets"]), key=str.casefold)
    return groups


def _decision_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if document.get("schema_version") != 1:
        raise ValueError("decision document schema_version must be 1")
    if document.get("approval_status") != "approved":
        raise ValueError("decision document approval_status must be approved")
    if not isinstance(document.get("approval_reference"), str) or not document[
        "approval_reference"
    ].strip():
        raise ValueError(
            "decision document approval_reference must identify the global "
            "taxonomy review"
        )
    rows = document.get("decisions")
    if not isinstance(rows, list):
        raise ValueError("decision document decisions must be a list")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"decisions[{index}] must be an object")
        candidate = row.get("candidate")
        action = row.get("action")
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError(f"decisions[{index}].candidate must be non-empty")
        if action not in {"add", "promote", "merge", "reject"}:
            raise ValueError(
                f"decisions[{index}].action must be add, promote, merge or reject"
            )
        key = normalize_tag_name(candidate)
        if key in result:
            raise ValueError(f"duplicate decision for {candidate}")
        canonical = row.get("canonical")
        if action == "merge" and (
            not isinstance(canonical, str) or not canonical.strip()
        ):
            raise ValueError(f"decisions[{index}].canonical is required")
        if action == "add" and canonical is not None and (
            not isinstance(canonical, str) or not canonical.strip()
        ):
            raise ValueError(f"decisions[{index}].canonical must be non-empty")
        candidate_id = row.get("candidate_id")
        if action == "promote" and (
            not isinstance(candidate_id, str) or not candidate_id.strip()
        ):
            raise ValueError(f"decisions[{index}].candidate_id is required")
        reason = row.get("reason")
        if action == "reject" and (
            not isinstance(reason, str) or not reason.strip()
        ):
            raise ValueError(f"decisions[{index}].reason is required")
        for field in ("aliases", "facets"):
            values = row.get(field, [])
            if not isinstance(values, list) or any(
                not isinstance(value, str) for value in values
            ):
                raise ValueError(f"decisions[{index}].{field} must be strings")
        result[key] = row
    return result


def _add_aliases(
    document: dict[str, Any],
    *,
    canonical: str,
    labels: list[str],
    approval_reference: str,
) -> tuple[dict[str, Any], list[str]]:
    catalogue = TagCatalogue(document)
    target = catalogue.resolve(tag_id=None, name=canonical)
    added: list[str] = []
    for label in _unique(labels):
        if normalize_tag_name(label) == normalize_tag_name(target.name):
            continue
        try:
            existing = catalogue.resolve(tag_id=None, name=label)
        except TagResolutionError as exc:
            if not str(exc).startswith("unknown tag name"):
                raise
            added.append(label.strip())
        else:
            if existing.id != target.id:
                raise ValueError(
                    f"alias {label!r} resolves to {existing.id} "
                    f"({existing.name}), not {target.id} ({target.name})"
                )
    if not added:
        return document, []
    updated = deepcopy(document)
    raw_target = next(tag for tag in updated["tags"] if tag["id"] == target.id)
    raw_target["aliases"] = _unique([*raw_target["aliases"], *added])
    raw_target["aliases"].sort(key=str.casefold)
    raw_target.setdefault("lifecycle", {})["last_alias_approval_reference"] = (
        approval_reference
    )
    TagCatalogue(updated)
    return updated, added


def _proposal_from_candidate(
    candidate: dict[str, Any],
    *,
    tag_id: str,
    tag_name: str,
) -> dict[str, Any]:
    raw_confidence = candidate.get("confidence")
    if isinstance(raw_confidence, dict):
        score = raw_confidence.get("score")
        supplied_band = raw_confidence.get("band")
        supplied_reason = raw_confidence.get("reason")
    else:
        score = raw_confidence
        supplied_band = None
        supplied_reason = None
    if not isinstance(score, int) or not 70 <= score <= 100:
        raise ValueError(f"{candidate.get('name')}: confidence must be 70-100")
    summary = candidate.get("summary")
    source_ids = candidate.get("source_ids")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{candidate.get('name')}: summary must be non-empty")
    if not isinstance(source_ids, list) or not source_ids:
        raise ValueError(f"{candidate.get('name')}: source_ids must be non-empty")
    band = "very_high" if score >= 95 else "high" if score >= 85 else "medium"
    if supplied_band is not None and supplied_band != band:
        raise ValueError(
            f"{candidate.get('name')}: confidence band does not match score {score}"
        )
    reason = (
        supplied_reason.strip()
        if isinstance(supplied_reason, str) and supplied_reason.strip()
        else (
            "The completed semantic review found a durable, material "
            "association directly supported by the cited dossier sources."
        )
    )
    return {
        "tag_id": tag_id,
        "name": tag_name,
        "summary": summary.strip(),
        "confidence": {
            "score": score,
            "band": band,
            "reason": reason,
        },
        "source_ids": source_ids,
    }


def prepare_resolution(
    catalogue_document: dict[str, Any],
    reviews: list[tuple[Path, dict[str, Any]]],
    decisions_document: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]], dict[str, Any]]:
    groups = _candidate_groups(reviews)
    decisions = _decision_map(decisions_document)
    missing = sorted(set(groups) - set(decisions))
    extras = sorted(set(decisions) - set(groups))
    if missing or extras:
        raise ValueError(
            f"candidate decisions do not match reviews; missing={missing}, extras={extras}"
        )

    updated_catalogue = deepcopy(catalogue_document)
    resolved: dict[str, dict[str, str]] = {}
    added_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    for key in sorted(groups):
        decision = decisions[key]
        if decision["action"] not in {"add", "promote"}:
            continue
        group = groups[key]
        aliases = _unique(
            [
                *group["aliases"],
                *group["candidate_names"],
                *decision.get("aliases", []),
            ]
        )
        if decision["action"] == "promote":
            updated, result = ADD_TAG.prepare_promotion(
                updated_catalogue,
                tag_id=decision["candidate_id"],
                approval_reference=decisions_document["approval_reference"],
            )
            canonical_name = result["name"]
            aliases = [
                alias
                for alias in aliases
                if normalize_tag_name(alias) != normalize_tag_name(canonical_name)
            ]
        else:
            canonical_name = (
                decision.get("canonical") or group["candidate_names"][0]
            )
            aliases = [
                alias
                for alias in aliases
                if normalize_tag_name(alias) != normalize_tag_name(canonical_name)
            ]
            facet_source = (
                decision["facets"] if "facets" in decision else group["facets"]
            )
            facets = sorted(set(facet_source), key=str.casefold)
            updated, result = ADD_TAG.prepare_addition(
                updated_catalogue,
                name=canonical_name,
                aliases=aliases,
                facets=facets,
                approval_reference=decisions_document["approval_reference"],
            )
        if updated is not None:
            updated_catalogue = updated
        updated_catalogue, added_aliases = _add_aliases(
            updated_catalogue,
            canonical=result["name"],
            labels=aliases,
            approval_reference=decisions_document["approval_reference"],
        )
        resolved[key] = {"id": result["id"], "name": result["name"]}
        added_rows.append(
            {
                "candidate": group["candidate_names"],
                "canonical": resolved[key],
                "status": result["status"],
                "aliases_added": added_aliases,
            }
        )

    catalogue = TagCatalogue(updated_catalogue)
    for key in sorted(groups):
        decision = decisions[key]
        if decision["action"] == "merge":
            target = decision["canonical"]
            tag = catalogue.resolve(tag_id=None, name=target)
            resolved[key] = {"id": tag.id, "name": tag.name}
            updated_catalogue, added_aliases = _add_aliases(
                updated_catalogue,
                canonical=tag.name,
                labels=[
                    *groups[key]["candidate_names"],
                    *groups[key]["aliases"],
                    *decision.get("aliases", []),
                ],
                approval_reference=decisions_document["approval_reference"],
            )
            catalogue = TagCatalogue(updated_catalogue)
            added_rows.append(
                {
                    "candidate": groups[key]["candidate_names"],
                    "canonical": resolved[key],
                    "status": "merged",
                    "aliases_added": added_aliases,
                }
            )
        elif decision["action"] == "reject":
            rejected_rows.append(
                {
                    "candidate": groups[key]["candidate_names"],
                    "reason": decision["reason"].strip(),
                }
            )

    updated_reviews = [(path, deepcopy(review)) for path, review in reviews]
    review_lookup = {str(path.resolve()): review for path, review in updated_reviews}
    for key, group in groups.items():
        decision = decisions[key]
        for occurrence in group["proposals"]:
            path = occurrence["review_path"]
            review = review_lookup[str(path.resolve())]
            candidate = occurrence["candidate"]
            if decision["action"] == "reject":
                review.setdefault("rejected_candidates", []).append(
                    {
                        "name": candidate["name"],
                        "reason": decision["reason"].strip(),
                    }
                )
            else:
                target = resolved[key]
                proposal = _proposal_from_candidate(
                    candidate,
                    tag_id=target["id"],
                    tag_name=target["name"],
                )
                existing = {
                    item.get("tag_id"): item
                    for item in review.get("canonical_tags", [])
                    if isinstance(item, dict)
                }
                if target["id"] in existing:
                    current = existing[target["id"]]
                    current["source_ids"] = list(
                        dict.fromkeys(
                            [*current.get("source_ids", []), *proposal["source_ids"]]
                        )
                    )
                    if proposal["confidence"]["score"] > current.get(
                        "confidence", {}
                    ).get("score", 0):
                        current["confidence"] = proposal["confidence"]
                else:
                    review.setdefault("canonical_tags", []).append(proposal)
                review["canonical_tags"].sort(
                    key=lambda item: str(item.get("name", "")).casefold()
                )
            review["catalogue_candidates"] = [
                item
                for item in review["catalogue_candidates"]
                if normalize_tag_name(str(item.get("name", ""))) != key
            ]

    report = {
        "candidate_group_count": len(groups),
        "added_or_reused": added_rows,
        "rejected": rejected_rows,
        "review_file_count": len(reviews),
    }
    return updated_catalogue, updated_reviews, report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=(
            "Centrally resolve legacy pre-closed-world semantic-review "
            "candidates into approved promotions, additions, merges or "
            "documented rejections."
        )
    )
    parser.add_argument("decisions", type=Path)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument(
        "--review-id",
        action="append",
        type=int,
        default=[],
        help="Resolve only this person_id; repeat for a stable checkpoint batch.",
    )
    parser.add_argument(
        "--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH
    )
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    catalogue_document = _load_object(args.catalogue)
    decisions_document = _load_object(args.decisions)
    reviews = [
        (path, _load_object(path))
        for path in sorted(args.reviews.glob("*.json"))
    ]
    if args.review_id:
        requested = set(args.review_id)
        selected = [
            (path, review)
            for path, review in reviews
            if review.get("person_id") in requested
        ]
        found = {review.get("person_id") for _, review in selected}
        missing_ids = sorted(requested - found)
        if missing_ids:
            raise ValueError(f"review checkpoints not found: {missing_ids}")
        reviews = selected
    updated_catalogue, updated_reviews, report = prepare_resolution(
        catalogue_document, reviews, decisions_document
    )
    generated_at = datetime.now(UTC)
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    audit_path = args.audit or (
        DEFAULT_AUDIT_DIR / f"candidate-resolution-{stamp}.json"
    )
    audit = {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "decision_file": str(args.decisions.resolve()),
        **report,
    }
    if args.apply:
        atomic_write_json(args.catalogue, updated_catalogue)
        for path, review in updated_reviews:
            atomic_write_json(path, review)
    atomic_write_json(audit_path, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"Audit report: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
