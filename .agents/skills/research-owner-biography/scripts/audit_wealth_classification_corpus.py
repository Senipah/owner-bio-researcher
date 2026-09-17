"""Audit corpus-wide HNWI Unknown classifications with hash-bound checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DOSSIERS = REPO_ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_AUDIT_DIR = (
    REPO_ROOT / "output" / "owner-research" / "wealth-classification-audit"
)
DEFAULT_CHECKPOINTS = DEFAULT_AUDIT_DIR / "reviews"
DEFAULT_REPORT = DEFAULT_AUDIT_DIR / "latest-report.json"

SCHEMA_VERSION = 1
SCOPE = "wealth-classification-backfill"
WEALTH_FIELDS = (
    "wealth_creation_industry",
    "primary_industry",
    "wealth_origin",
    "wealth_relationship",
)
TERMINAL_DECISION = "retain_unknown"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unknown_fields(dossier: dict[str, Any]) -> list[str]:
    return [
        field
        for field in WEALTH_FIELDS
        if isinstance(dossier.get(field), dict)
        and dossier[field].get("classification") == "unknown"
    ]


def _priority_reasons(dossier: dict[str, Any], unknown_fields: list[str]) -> list[str]:
    reasons: list[str] = []
    relationship = dossier.get("wealth_relationship", {}).get("classification")
    creation = dossier.get("wealth_creation_industry", {}).get("classification")
    if "primary_industry" in unknown_fields and creation not in {None, "unknown"}:
        reasons.append("primary_origin_sector_fallback_required")
    if "wealth_origin" in unknown_fields and relationship == "founder":
        reasons.append("founder_built_origin_review")
    if "wealth_origin" in unknown_fields and relationship == "heir_family_shareholder":
        reasons.append("family_transfer_origin_review")
    if len(unknown_fields) == len(WEALTH_FIELDS):
        reasons.append("all_four_fields_unknown")
    return reasons


def build_pending_checkpoint(path: Path, dossier: dict[str, Any]) -> dict[str, Any]:
    unknown_fields = _unknown_fields(dossier)
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "status": "pending",
        "person_id": dossier.get("owner", {}).get("person_id"),
        "display_name": dossier.get("owner", {}).get("display_name"),
        "dossier_path": path.as_posix(),
        "dossier_sha256": _sha256(path),
        "unknown_fields": unknown_fields,
        "priority_reasons": _priority_reasons(dossier, unknown_fields),
        "decisions": {},
    }


def bootstrap_pending_reviews(
    dossiers: Path, checkpoints: Path
) -> dict[str, int]:
    checkpoints.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    for path in sorted(dossiers.glob("*.research.json")):
        dossier = _load_object(path)
        unknown_fields = _unknown_fields(dossier)
        if dossier.get("record_type") != "person" or not unknown_fields:
            continue
        person_id = dossier.get("owner", {}).get("person_id")
        if not isinstance(person_id, int):
            raise ValueError(f"{path}: person dossier requires integer person_id")
        target = checkpoints / f"{person_id}.json"
        if target.exists():
            existing = _load_object(target)
            if existing.get("status") == "reviewed":
                counts["preserved_reviewed"] += 1
                continue
            counts["refreshed_pending"] += 1
        else:
            counts["created_pending"] += 1
        target.write_text(
            json.dumps(build_pending_checkpoint(path, dossier), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    return dict(sorted(counts.items()))


def _strongest_alternative(dossier: dict[str, Any], field: str) -> str:
    for candidate in dossier.get("candidates_requiring_review", []):
        if not isinstance(candidate, dict):
            continue
        candidate_field = candidate.get("field") or candidate.get("candidate_type")
        if candidate_field != field:
            continue
        value = (
            candidate.get("candidate_value")
            or candidate.get("classification")
            or candidate.get("label")
            or "the recorded candidate"
        )
        explanation = candidate.get("reason")
        if not isinstance(explanation, str):
            explanation = candidate.get("confidence", {}).get("reason")
        if not isinstance(explanation, str):
            explanation = "the dossier does not establish every material premise"
        return f"{value} was the strongest recorded alternative, but {explanation}"

    creation = dossier.get("wealth_creation_industry", {}).get("label")
    relationship = dossier.get("wealth_relationship", {}).get("classification")
    if field == "wealth_creation_industry":
        return (
            "The documented career and business sectors were considered, but none "
            "is established as materially creating the principal personal wealth."
        )
    if field == "primary_industry":
        if creation and creation != "Unknown":
            return (
                f"{creation} was considered as the origin-sector fallback, but the "
                "dossier's retained-Unknown rationale prevents that fallback from "
                "honestly describing the current principal asset base."
            )
        return (
            "The documented current sectors were considered, but none is tied to a "
            "principal personally attributable asset and no creation-sector fallback applies."
        )
    if field == "wealth_origin":
        if relationship == "founder":
            return (
                "Broad Self-made was considered from the founder evidence, but the "
                "dossier does not establish the required material link to the principal fortune."
            )
        if relationship == "heir_family_shareholder":
            return (
                "Marriage / family transfer was considered from the family-shareholder "
                "relationship, but the dossier does not establish the required succession "
                "and personal economic-interest premises."
            )
        return (
            "Self-made, transfer-based and mixed origin values were considered, but no "
            "available value has every material premise supported at confidence 70 or higher."
        )
    return (
        "Founder, operator, investor, family-shareholder, beneficiary and custodial "
        "relationships were considered, but none is established for a principal "
        "personally attributable wealth-producing asset."
    )


def record_retained_reviews(
    dossiers: Path, checkpoints: Path, person_ids: list[int]
) -> dict[str, int]:
    """Record an already-completed human audit for dossiers retaining Unknown.

    This is deliberately explicit per person. It does not decide classifications or
    perform research; it serialises the dossier's current evidence rationale after
    the main agent has reviewed and accepted the retained-Unknown decision.
    """

    checkpoints.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    for person_id in person_ids:
        path = dossiers / f"{person_id}.research.json"
        if not path.exists():
            raise ValueError(f"No dossier found for person_id {person_id}: {path}")
        dossier = _load_object(path)
        owner = dossier.get("owner", {})
        if dossier.get("record_type") != "person" or owner.get("person_id") != person_id:
            raise ValueError(f"{path}: person_id or record_type mismatch")
        unknown_fields = _unknown_fields(dossier)
        if not unknown_fields:
            raise ValueError(f"{path}: no retained Unknown field to review")

        checkpoint = build_pending_checkpoint(path, dossier)
        checkpoint["status"] = "reviewed"
        decisions: dict[str, Any] = {}
        for field in unknown_fields:
            value = dossier[field]
            summary = value.get("summary")
            confidence_reason = value.get("confidence", {}).get("reason")
            if not isinstance(summary, str) or not isinstance(confidence_reason, str):
                raise ValueError(f"{path}: {field} requires summary and confidence reason")
            source_ids = value.get("source_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise ValueError(f"{path}: {field} requires existing source IDs")
            decisions[field] = {
                "decision": TERMINAL_DECISION,
                "reason": (
                    "Retained Unknown after amended-policy review. "
                    f"{summary} {confidence_reason}"
                ),
                "strongest_alternative": _strongest_alternative(dossier, field),
                "source_ids": source_ids,
                "policy_checks": {
                    "direct_evidence_checked": True,
                    "reasoned_inference_checked": True,
                    "less_specific_value_checked": True,
                    "silence_not_used": True,
                },
            }
        checkpoint["decisions"] = decisions
        target = checkpoints / f"{person_id}.json"
        target.write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        counts["recorded_reviewed"] += 1
    return dict(sorted(counts.items()))


def _validate_review(
    checkpoint_path: Path,
    checkpoint: dict[str, Any],
    dossier_path: Path,
    dossier: dict[str, Any],
    unknown_fields: list[str],
) -> list[str]:
    errors: list[str] = []
    owner = dossier.get("owner", {})
    expected = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "status": "reviewed",
        "person_id": owner.get("person_id"),
        "display_name": owner.get("display_name"),
        "dossier_sha256": _sha256(dossier_path),
        "unknown_fields": unknown_fields,
    }
    for key, value in expected.items():
        if checkpoint.get(key) != value:
            errors.append(
                f"{checkpoint_path}: {key} must equal {value!r}; "
                f"found {checkpoint.get(key)!r}"
            )

    decisions = checkpoint.get("decisions")
    if not isinstance(decisions, dict):
        errors.append(f"{checkpoint_path}: decisions must be an object")
        return errors
    if set(decisions) != set(unknown_fields):
        errors.append(
            f"{checkpoint_path}: decisions must cover exactly {unknown_fields!r}"
        )

    known_source_ids = {
        source.get("id")
        for source in dossier.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("id"), str)
    }
    required_checks = {
        "direct_evidence_checked",
        "reasoned_inference_checked",
        "less_specific_value_checked",
        "silence_not_used",
    }
    for field in unknown_fields:
        decision = decisions.get(field)
        prefix = f"{checkpoint_path}: decisions.{field}"
        if not isinstance(decision, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if decision.get("decision") != TERMINAL_DECISION:
            errors.append(f"{prefix}.decision must be {TERMINAL_DECISION!r}")
        for key in ("reason", "strongest_alternative"):
            value = decision.get(key)
            if not isinstance(value, str) or len(value.strip()) < 20:
                errors.append(f"{prefix}.{key} must contain a substantive explanation")
        source_ids = decision.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            errors.append(f"{prefix}.source_ids must be a non-empty list")
        elif any(source_id not in known_source_ids for source_id in source_ids):
            errors.append(f"{prefix}.source_ids contains an unknown dossier source")
        checks = decision.get("policy_checks")
        if not isinstance(checks, dict) or set(checks) != required_checks:
            errors.append(f"{prefix}.policy_checks must contain {sorted(required_checks)!r}")
        elif any(checks[key] is not True for key in required_checks):
            errors.append(f"{prefix}.policy_checks values must all be true")
    return errors


def audit_corpus(dossiers: Path, checkpoints: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    status_counts: Counter[str] = Counter()
    record_type_counts: Counter[str] = Counter()
    unknown_field_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()

    for path in sorted(dossiers.glob("*.research.json")):
        dossier = _load_object(path)
        record_type = dossier.get("record_type")
        record_type_counts[str(record_type)] += 1
        unknown_fields = _unknown_fields(dossier)
        unknown_field_counts.update(unknown_fields)
        priorities = _priority_reasons(dossier, unknown_fields)
        priority_counts.update(priorities)
        owner = dossier.get("owner", {})
        row = {
            "person_id": owner.get("person_id"),
            "display_name": owner.get("display_name"),
            "record_type": record_type,
            "dossier": path.as_posix(),
            "dossier_sha256": _sha256(path),
            "unknown_fields": unknown_fields,
            "priority_reasons": priorities,
        }

        if not unknown_fields:
            status = "no_unknown_fields"
        elif record_type != "person":
            status = "non_person_not_applicable"
        else:
            person_id = owner.get("person_id")
            checkpoint_path = checkpoints / f"{person_id}.json"
            if not checkpoint_path.exists():
                status = "pending_review"
            else:
                checkpoint = _load_object(checkpoint_path)
                if checkpoint.get("status") != "reviewed":
                    status = "pending_review"
                else:
                    review_errors = _validate_review(
                        checkpoint_path,
                        checkpoint,
                        path,
                        dossier,
                        unknown_fields,
                    )
                    if review_errors:
                        errors.extend(review_errors)
                        status = "invalid_or_stale_review"
                    else:
                        status = "reviewed_retained_unknown"
                row["checkpoint"] = checkpoint_path.as_posix()

        row["status"] = status
        status_counts[status] += 1
        rows.append(row)

    fallback_violations = [
        row
        for row in rows
        if "primary_origin_sector_fallback_required" in row["priority_reasons"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "dossier_directory": dossiers.resolve().as_posix(),
        "checkpoint_directory": checkpoints.resolve().as_posix(),
        "summary": {
            "dossier_count": len(rows),
            "record_types": dict(sorted(record_type_counts.items())),
            "unknown_fields": {
                field: unknown_field_counts.get(field, 0) for field in WEALTH_FIELDS
            },
            "statuses": dict(sorted(status_counts.items())),
            "priority_reasons": dict(sorted(priority_counts.items())),
            "fallback_violation_count": len(fallback_violations),
            "error_count": len(errors),
        },
        "errors": errors,
        "rows": rows,
    }


def _is_complete(report: dict[str, Any]) -> bool:
    summary = report["summary"]
    statuses = summary["statuses"]
    return (
        summary["error_count"] == 0
        and summary["fallback_violation_count"] == 0
        and statuses.get("pending_review", 0) == 0
        and statuses.get("invalid_or_stale_review", 0) == 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory HNWI Unknown fields and verify one hash-bound terminal "
            "checkpoint for every person dossier that retains an Unknown."
        )
    )
    parser.add_argument("--dossiers", type=Path, default=DEFAULT_DOSSIERS)
    parser.add_argument("--checkpoints", type=Path, default=DEFAULT_CHECKPOINTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument(
        "--review-retained",
        type=int,
        action="append",
        default=[],
        metavar="PERSON_ID",
        help=(
            "After the main agent has manually accepted a dossier's retained Unknown "
            "decision, write its hash-bound reviewed checkpoint; repeat per person."
        ),
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    bootstrap = None
    if args.bootstrap:
        bootstrap = bootstrap_pending_reviews(args.dossiers, args.checkpoints)
    recorded = None
    if args.review_retained:
        recorded = record_retained_reviews(
            args.dossiers, args.checkpoints, args.review_retained
        )
    report = audit_corpus(args.dossiers, args.checkpoints)
    if bootstrap is not None:
        report["bootstrap"] = bootstrap
    if recorded is not None:
        report["recorded_reviews"] = recorded
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {args.report.resolve()}")
    if args.strict and not _is_complete(report):
        print("Wealth-classification corpus audit is incomplete.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
