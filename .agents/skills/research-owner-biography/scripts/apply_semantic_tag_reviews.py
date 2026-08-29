from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, TagCatalogue, load_tag_catalogue


DEFAULT_DOSSIER_DIR = REPO_ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_REVIEW_DIR = (
    REPO_ROOT / "output" / "owner-research" / "tag-semantic-review" / "reviews"
)
DEFAULT_AUDIT_DIR = REPO_ROOT / "output" / "owner-research" / "tag-semantic-review"
EXCLUDED_NAMES = {
    "Arts & culture philanthropy",
    "Children & youth philanthropy",
    "Education philanthropy",
    "Family business",
    "Family office",
    "Health philanthropy",
    "Philanthropy",
    "Property development",
    "Science philanthropy",
}
GRANULAR_GAMBLING_NAMES = {
    "Bookmaking",
    "Casino operations",
    "Gaming machines",
    "Lotteries",
    "Online gambling & betting",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _band(score: int) -> str:
    if score >= 95:
        return "very_high"
    if score >= 85:
        return "high"
    if score >= 70:
        return "medium"
    return "low"


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: could not load JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: root must be an object")
    return value


def _validate_confidence(
    value: Any,
    *,
    path: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    score = value.get("score")
    reason = value.get("reason")
    if not isinstance(score, int) or not 70 <= score <= 100:
        raise ValueError(f"{path}.score must be an integer from 70 to 100")
    if value.get("band") != _band(score):
        raise ValueError(f"{path}.band does not match score {score}")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"{path}.reason must be non-empty")
    return {
        "score": score,
        "band": value["band"],
        "reason": reason.strip(),
    }


def _validate_review(
    review_path: Path,
    dossier_path: Path,
    dossier: dict[str, Any],
    catalogue: TagCatalogue,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    review = _load_object(review_path)
    prefix = str(review_path)
    if review.get("schema_version") != 1:
        raise ValueError(f"{prefix}: schema_version must be 1")
    if review.get("status") != "reviewed":
        raise ValueError(f"{prefix}: status must be 'reviewed'")

    owner = dossier.get("owner")
    if not isinstance(owner, dict):
        raise ValueError(f"{dossier_path}: owner must be an object")
    person_id = owner.get("person_id")
    display_name = owner.get("display_name")
    if review.get("person_id") != person_id:
        raise ValueError(f"{prefix}: person_id does not match dossier")
    if review.get("display_name") != display_name:
        raise ValueError(f"{prefix}: display_name does not match dossier")
    if review.get("dossier_sha256") != _sha256(dossier_path):
        raise ValueError(f"{prefix}: dossier_sha256 is stale")

    candidates = review.get("catalogue_candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"{prefix}: catalogue_candidates must be a list")
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or not isinstance(
            candidate.get("name"), str
        ):
            raise ValueError(
                f"{prefix}: catalogue_candidates[{index}] must name a candidate"
            )

    source_ids = {
        source.get("id")
        for source in dossier.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    proposals = review.get("canonical_tags")
    if not isinstance(proposals, list):
        raise ValueError(f"{prefix}: canonical_tags must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, proposal in enumerate(proposals):
        item_path = f"{prefix}: canonical_tags[{index}]"
        if not isinstance(proposal, dict):
            raise ValueError(f"{item_path} must be an object")
        tag = catalogue.resolve(
            tag_id=proposal.get("tag_id"),
            name=str(proposal.get("name", "")),
        )
        if tag.id in seen:
            raise ValueError(f"{item_path} duplicates {tag.id} ({tag.name})")
        if tag.name in EXCLUDED_NAMES:
            raise ValueError(f"{item_path} uses deliberately excluded {tag.name}")
        seen.add(tag.id)
        summary = proposal.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(f"{item_path}.summary must be non-empty")
        confidence = _validate_confidence(
            proposal.get("confidence"), path=f"{item_path}.confidence"
        )
        cited = proposal.get("source_ids")
        if (
            not isinstance(cited, list)
            or not cited
            or any(not isinstance(source_id, str) for source_id in cited)
        ):
            raise ValueError(f"{item_path}.source_ids must be a non-empty list")
        missing = [source_id for source_id in cited if source_id not in source_ids]
        if missing:
            raise ValueError(
                f"{item_path}.source_ids are absent from dossier: {missing}"
            )
        normalized.append(
            {
                "tag_id": tag.id,
                "name": tag.name,
                "summary": summary.strip(),
                "confidence": confidence,
                "source_ids": list(dict.fromkeys(cited)),
            }
        )

    if dossier.get("record_type") == "unresolved_placeholder":
        unresolved_names = {proposal["name"] for proposal in normalized}
        if candidates or unresolved_names - {"Government-owned"}:
            raise ValueError(
                f"{prefix}: unresolved placeholders cannot have tags "
                "other than a separately evidenced Government-owned status"
            )
        if normalized:
            basis = review.get("government_owned_basis")
            if not isinstance(basis, str) or not basis.strip():
                raise ValueError(
                    f"{prefix}: Government-owned on an unresolved public-entity "
                    "label requires government_owned_basis"
                )
    elif not normalized and not candidates:
        reason = review.get("zero_tag_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                f"{prefix}: a reviewed empty set requires zero_tag_reason"
            )
    names = {proposal["name"] for proposal in normalized}
    granular_gambling = names & GRANULAR_GAMBLING_NAMES
    if granular_gambling and "Gambling" not in names:
        raise ValueError(
            f"{prefix}: granular gambling tags require Gambling: "
            f"{sorted(granular_gambling)}"
        )
    if "Government-owned" in names and dossier.get("record_type") not in {
        "institution",
        "unresolved_placeholder",
    }:
        raise ValueError(
            f"{prefix}: Government-owned requires an institution or explicitly "
            "evidenced unresolved public-entity owner record"
        )
    return normalized, candidates


def prepare_reviews(
    dossier_directory: Path,
    review_directory: Path,
    catalogue: TagCatalogue,
) -> dict[str, Any]:
    dossier_paths = sorted(dossier_directory.glob("*.research.json"))
    review_paths = sorted(review_directory.glob("*.json"))
    review_by_id: dict[int, Path] = {}
    for path in review_paths:
        try:
            person_id = int(path.stem)
        except ValueError as exc:
            raise ValueError(f"{path}: filename must be a numeric person ID") from exc
        if person_id in review_by_id:
            raise ValueError(f"duplicate review for owner {person_id}")
        review_by_id[person_id] = path

    rows: list[dict[str, Any]] = []
    dossier_ids: set[int] = set()
    errors: list[str] = []
    for dossier_path in dossier_paths:
        dossier = _load_object(dossier_path)
        owner = dossier.get("owner", {})
        person_id = owner.get("person_id")
        if not isinstance(person_id, int):
            errors.append(f"{dossier_path}: owner.person_id must be an integer")
            continue
        dossier_ids.add(person_id)
        review_path = review_by_id.get(person_id)
        if review_path is None:
            rows.append(
                {
                    "person_id": person_id,
                    "display_name": owner.get("display_name"),
                    "status": "pending_review",
                    "dossier": str(dossier_path),
                }
            )
            continue
        try:
            proposed_tags, candidates = _validate_review(
                review_path, dossier_path, dossier, catalogue
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue
        existing = dossier.get("proposed_tags")
        if not isinstance(existing, list):
            errors.append(f"{dossier_path}: proposed_tags must be a list")
            continue
        rows.append(
            {
                "person_id": person_id,
                "display_name": owner.get("display_name"),
                "status": (
                    "unresolved_catalogue_candidates"
                    if candidates
                    else "reviewed_changed"
                    if existing != proposed_tags
                    else "reviewed_unchanged"
                ),
                "dossier": str(dossier_path),
                "review": str(review_path),
                "before": existing,
                "after": proposed_tags,
                "catalogue_candidates": candidates,
            }
        )

    extras = sorted(set(review_by_id) - dossier_ids)
    if extras:
        errors.append(f"reviews have no matching dossier: {extras}")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "dossier_count": len(dossier_paths),
        "review_count": len(review_paths),
        "rows": rows,
    }


def _verify_backup(source: Path, backup: Path) -> None:
    source_files = sorted(path.name for path in source.glob("*.research.json"))
    backup_files = sorted(path.name for path in backup.glob("*.research.json"))
    if source_files != backup_files:
        raise ValueError("backup dossier inventory does not match source")
    for name in source_files:
        if _sha256(source / name) != _sha256(backup / name):
            raise ValueError(f"backup verification failed for {name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate semantic owner-tag review decisions and atomically apply "
            "them after every dossier has a terminal review."
        )
    )
    parser.add_argument("--dossiers", type=Path, default=DEFAULT_DOSSIER_DIR)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument(
        "--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH
    )
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    catalogue = load_tag_catalogue(args.catalogue)
    prepared = prepare_reviews(args.dossiers, args.reviews, catalogue)
    rows = prepared["rows"]
    counts = Counter(row["status"] for row in rows)
    reviewed = prepared["review_count"]
    dossier_count = prepared["dossier_count"]
    generated_at = datetime.now(UTC)
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    audit_path = args.audit or (
        DEFAULT_AUDIT_DIR
        / f"semantic-tag-review-{'apply' if args.apply else 'dry-run'}-{stamp}.json"
    )
    audit: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at.isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "dossier_directory": str(args.dossiers.resolve()),
        "review_directory": str(args.reviews.resolve()),
        "catalogue": catalogue.source_reference,
        "dossier_count": dossier_count,
        "review_count": reviewed,
        "status_counts": dict(sorted(counts.items())),
        "rows": rows,
    }

    if args.apply:
        if reviewed != dossier_count or counts.get("pending_review"):
            parser.error(
                f"--apply requires one review for every dossier; "
                f"found {reviewed} of {dossier_count}"
            )
        if counts.get("unresolved_catalogue_candidates"):
            parser.error("--apply requires all catalogue candidates to be resolved")
        changed = [row for row in rows if row["status"] == "reviewed_changed"]
        backup = args.backup or args.dossiers.with_name(
            f"{args.dossiers.name}-semantic-tag-backup-{stamp}"
        )
        if backup.exists():
            parser.error(f"backup path already exists: {backup}")
        shutil.copytree(args.dossiers, backup)
        _verify_backup(args.dossiers, backup)
        for row in changed:
            path = Path(row["dossier"])
            dossier = _load_object(path)
            dossier["proposed_tags"] = row["after"]
            atomic_write_json(path, dossier)
            verified = _load_object(path)
            if verified.get("proposed_tags") != row["after"]:
                raise ValueError(f"post-write verification failed for {path}")
        audit["backup_directory"] = str(backup.resolve())
        audit["backup_verified"] = True
        audit["written_dossier_count"] = len(changed)

    atomic_write_json(audit_path, audit)
    print(json.dumps({key: value for key, value in audit.items() if key != "rows"}, indent=2))
    print(f"Audit report: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
