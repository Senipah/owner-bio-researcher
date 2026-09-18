from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
for import_path in (REPO_ROOT, SCRIPT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from register_corpus_tag_candidates import prepare_registration
from src.io_utils import atomic_write_json
from src.owner_tags import USABLE_RECORD_TYPES, USABLE_RESEARCH_STATUSES, USABLE_REVIEW_STATUSES
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, TagCatalogue


DEFAULT_DOSSIER_ROOT = REPO_ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_AUDIT_ROOT = REPO_ROOT / "output" / "owner-research" / "tag-manifest-backfill"
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
STOP_WORDS = {
    "about",
    "after",
    "against",
    "alongside",
    "among",
    "built",
    "business",
    "company",
    "continues",
    "created",
    "creating",
    "current",
    "defining",
    "developed",
    "expanded",
    "family",
    "founded",
    "founder",
    "group",
    "helped",
    "identifiable",
    "including",
    "international",
    "later",
    "leads",
    "long",
    "made",
    "making",
    "network",
    "operated",
    "operating",
    "operation",
    "operator",
    "owner",
    "owned",
    "owns",
    "platform",
    "principal",
    "record",
    "remains",
    "role",
    "sale",
    "service",
    "serves",
    "sold",
    "substantial",
    "through",
    "under",
    "wealth",
    "whose",
    "with",
    "year",
}
CONCEPT_KEYWORDS = {
    "Marina operations": {
        "marina",
        "harbour",
        "harbor",
        "boatyard",
        "dock",
        "berth",
    },
    "Private healthcare providers": {
        "care",
        "clinic",
        "health",
        "healthcare",
        "homehealth",
        "hospice",
        "hospital",
        "medical",
        "nursing",
        "patient",
        "rehabilitation",
        "residential",
        "senior",
        "surgery",
    },
    "Education & training providers": {
        "academy",
        "course",
        "education",
        "learning",
        "school",
        "training",
        "university",
        "vocational",
    },
    "Footwear": {
        "boot",
        "footwear",
        "rainfair",
        "shoe",
    },
}


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _stem(token: str) -> str:
    value = token.casefold()
    if len(value) > 5 and value.endswith("ies"):
        return value[:-3] + "y"
    if len(value) > 4 and value.endswith("s") and not value.endswith("ss"):
        return value[:-1]
    return value


def _tokens(value: str) -> set[str]:
    return {
        _stem(token)
        for token in TOKEN_RE.findall(value)
        if len(token) >= 4 and _stem(token) not in STOP_WORDS
    }


def _text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text_content(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text_content(item) for item in value.values())
    return ""


def _evidence_source_ids(
    dossier: dict[str, Any],
    *,
    concept_name: str,
    membership_basis: str,
) -> list[str]:
    sources = dossier.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("dossier.sources must be a non-empty list")
    owner = dossier.get("owner", {})
    owner_tokens = _tokens(str(owner.get("display_name", "")))
    basis_tokens = _tokens(membership_basis) - owner_tokens
    keyword_tokens = {_stem(item) for item in CONCEPT_KEYWORDS.get(concept_name, set())}

    keyword_scored: list[tuple[int, int, int, str]] = []
    basis_scored: list[tuple[int, int, int, str]] = []
    known_source_ids: set[str] = set()
    for order, source in enumerate(sources):
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            continue
        source_id = source["id"]
        known_source_ids.add(source_id)
        source_tokens = _tokens(
            " ".join(
                (
                    str(source.get("title", "")),
                    str(source.get("publisher", "")),
                    _text_content(source.get("supports", [])),
                )
            )
        )
        keyword_hits = len(source_tokens & keyword_tokens)
        basis_hits = len(source_tokens & basis_tokens)
        score = keyword_hits * 10 + min(basis_hits, 6)
        tier = source.get("tier") if isinstance(source.get("tier"), int) else 99
        row = (-score, tier, order, source_id)
        if keyword_hits:
            keyword_scored.append(row)
        elif basis_hits:
            basis_scored.append(row)

    if keyword_scored:
        selected = [item[3] for item in sorted(keyword_scored)[:3]]
    else:
        selected = [item[3] for item in sorted(basis_scored)[:2]]
    if not selected:
        fallback: list[str] = []
        for field in ("biography", "long_biography", "biography_brief"):
            section = dossier.get(field)
            if not isinstance(section, dict):
                continue
            cited = section.get("source_ids")
            if isinstance(cited, list):
                fallback.extend(
                    item for item in cited if isinstance(item, str) and item
                )
        selected = list(dict.fromkeys(fallback))[:5]
    missing = [source_id for source_id in selected if source_id not in known_source_ids]
    if missing:
        raise ValueError(f"selected source IDs are absent from dossier: {missing}")
    if not selected:
        raise ValueError("no evidence source IDs could be selected")
    return selected


def _confidence(dossier: dict[str, Any], source_ids: list[str]) -> dict[str, Any]:
    selected = set(source_ids)
    tiers = [
        source.get("tier")
        for source in dossier.get("sources", [])
        if isinstance(source, dict)
        and source.get("id") in selected
        and isinstance(source.get("tier"), int)
    ]
    best_tier = min(tiers) if tiers else None
    if best_tier == 1:
        score = 95
        evidence = "including tier-1 evidence"
    elif best_tier == 2:
        score = 90
        evidence = "including strong independent evidence"
    else:
        score = 85
        evidence = "from the accepted research record"
    return {
        "score": score,
        "band": "very_high" if score >= 95 else "high",
        "reason": (
            "The approved corpus-level review found that the cited dossier "
            f"sources, {evidence}, satisfy the tag's explicit membership and "
            "exclusion contract."
        ),
    }


def _validate_dossier_state(dossier: dict[str, Any], path: Path) -> None:
    owner = dossier.get("owner")
    if not isinstance(owner, dict):
        raise ValueError(f"{path}: owner must be an object")
    if dossier.get("schema_version") != 8:
        raise ValueError(f"{path}: schema_version must be 8")
    if dossier.get("record_type") not in USABLE_RECORD_TYPES:
        raise ValueError(f"{path}: record_type is not tag-assignable")
    if dossier.get("research_status") not in USABLE_RESEARCH_STATUSES:
        raise ValueError(f"{path}: research_status is not usable")
    review = dossier.get("review")
    review_status = review.get("status") if isinstance(review, dict) else None
    if review_status not in USABLE_REVIEW_STATUSES:
        raise ValueError(f"{path}: review.status is not complete or approved")
    if not isinstance(dossier.get("proposed_tags"), list):
        raise ValueError(f"{path}: proposed_tags must be a list")


def prepare_backfill(
    manifest: dict[str, Any],
    catalogue_document: dict[str, Any],
    *,
    repo_root: Path = REPO_ROOT,
    dossier_root: Path = DEFAULT_DOSSIER_ROOT,
) -> dict[str, Any]:
    """Prepare exact, additive dossier changes for one approved manifest."""
    _, registration_report = prepare_registration(catalogue_document, manifest)
    if any(
        result["outcome"] != "existing_lifecycle_record"
        for result in registration_report["results"]
    ):
        raise ValueError("every manifest concept must already exist in the catalogue")
    catalogue = TagCatalogue(catalogue_document)
    resolved_root = dossier_root.resolve()

    manifest_ids: set[int] = set()
    rows: list[dict[str, Any]] = []
    tag_ids: set[str] = set()
    for concept in manifest["concepts"]:
        tag = catalogue.resolve(tag_id=None, name=concept["name"])
        if tag.status != "active":
            raise ValueError(
                f"{tag.id} ({tag.name}) must be active before dossier backfill"
            )
        tag_ids.add(tag.id)
        for record in concept["dossier_records"]:
            person_id = record["person_id"]
            if person_id in manifest_ids:
                raise ValueError(
                    f"owner {person_id} appears under more than one manifest concept"
                )
            manifest_ids.add(person_id)
            raw_path = Path(record["dossier"])
            path = (repo_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
            if not path.is_relative_to(resolved_root):
                raise ValueError(f"{path}: dossier is outside {resolved_root}")
            dossier = _load_object(path)
            _validate_dossier_state(dossier, path)
            owner = dossier["owner"]
            if owner.get("person_id") != person_id:
                raise ValueError(f"{path}: owner.person_id does not match manifest")

            existing = dossier["proposed_tags"]
            conflicting = [
                item
                for item in existing
                if isinstance(item, dict)
                and (item.get("tag_id") == tag.id or item.get("name") == tag.name)
            ]
            source_ids = _evidence_source_ids(
                dossier,
                concept_name=concept["name"],
                membership_basis=record["membership_basis"],
            )
            proposal = {
                "tag_id": tag.id,
                "name": tag.name,
                "summary": record["membership_basis"],
                "confidence": _confidence(dossier, source_ids),
                "source_ids": source_ids,
                "taxonomy_value": concept["semantic_contract"]["membership"],
            }
            if conflicting:
                if len(conflicting) != 1 or conflicting[0] != proposal:
                    raise ValueError(
                        f"{path}: existing {tag.name} assignment differs from "
                        "the reviewed manifest proposal"
                    )
                after = existing
                status = "unchanged"
            else:
                after = [*existing, proposal]
                status = "add"
            rows.append(
                {
                    "person_id": person_id,
                    "display_name": owner.get("display_name"),
                    "tag_id": tag.id,
                    "tag_name": tag.name,
                    "dossier": str(path),
                    "status": status,
                    "before": existing,
                    "after": after,
                    "proposal": proposal,
                }
            )

    unexpected: list[dict[str, Any]] = []
    for path in sorted(resolved_root.glob("*.research.json")):
        dossier = _load_object(path)
        owner = dossier.get("owner", {})
        person_id = owner.get("person_id") if isinstance(owner, dict) else None
        if person_id in manifest_ids:
            continue
        for proposal in dossier.get("proposed_tags", []):
            if isinstance(proposal, dict) and proposal.get("tag_id") in tag_ids:
                unexpected.append(
                    {
                        "person_id": person_id,
                        "dossier": str(path.resolve()),
                        "tag_id": proposal.get("tag_id"),
                        "tag_name": proposal.get("name"),
                    }
                )
    if unexpected:
        raise ValueError(
            "non-manifest dossiers already contain target tag assignments: "
            + json.dumps(unexpected, ensure_ascii=True)
        )

    counts = Counter(row["status"] for row in rows)
    return {
        "manifest_record_count": len(rows),
        "distinct_owner_count": len(manifest_ids),
        "concept_count": len(tag_ids),
        "status_counts": dict(sorted(counts.items())),
        "unexpected_non_manifest_assignments": unexpected,
        "rows": rows,
    }


def _copy_and_verify(rows: list[dict[str, Any]], backup: Path) -> None:
    backup.mkdir(parents=True)
    for row in rows:
        source = Path(row["dossier"])
        target = backup / source.name
        if target.exists():
            raise ValueError(f"backup target already exists: {target}")
        shutil.copy2(source, target)
        if _sha256(source) != _sha256(target):
            raise ValueError(f"backup verification failed for {source}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or add exactly the reviewed active-tag memberships from a "
            "corpus candidate manifest while preserving every existing assignment."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH
    )
    parser.add_argument("--dossiers", type=Path, default=DEFAULT_DOSSIER_ROOT)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.apply and args.audit is None:
        parser.error("--apply requires --audit")
    if args.apply and args.backup is None:
        parser.error("--apply requires --backup")

    manifest = _load_object(args.manifest)
    catalogue_document = _load_object(args.catalogue)
    prepared = prepare_backfill(
        manifest,
        catalogue_document,
        repo_root=REPO_ROOT,
        dossier_root=args.dossiers,
    )
    generated_at = datetime.now(UTC).isoformat()
    audit = {
        "schema_version": 1,
        "generated_at": generated_at,
        "mode": "apply" if args.apply else "dry-run",
        "manifest": str(args.manifest.resolve()),
        "catalogue": str(args.catalogue.resolve()),
        "dossier_directory": str(args.dossiers.resolve()),
        **prepared,
    }

    if args.apply:
        changed = [row for row in prepared["rows"] if row["status"] == "add"]
        if args.backup.exists():
            parser.error(f"backup path already exists: {args.backup}")
        _copy_and_verify(changed, args.backup)
        for row in changed:
            path = Path(row["dossier"])
            dossier = _load_object(path)
            dossier["proposed_tags"] = row["after"]
            atomic_write_json(path, dossier)
            verified = _load_object(path)
            if verified.get("proposed_tags") != row["after"]:
                raise ValueError(f"post-write verification failed for {path}")
        audit["backup_directory"] = str(args.backup.resolve())
        audit["backup_verified"] = True
        audit["written_dossier_count"] = len(changed)

    if args.audit is not None:
        atomic_write_json(args.audit, audit)
    summary = {key: value for key, value in audit.items() if key != "rows"}
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if not args.apply:
        print("Dry-run only; no dossier state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
