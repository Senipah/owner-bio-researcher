from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, TagCatalogue


DEFAULT_BASELINE_REF = "6982498"
DEFAULT_SOURCE_RUN = "1ccfc30"


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _load_git_catalogue(reference: str, catalogue_path: Path) -> dict[str, Any]:
    relative = catalogue_path.resolve().relative_to(REPO_ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"{reference}:{relative}"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            f"Could not read approved baseline {reference}:{relative}: "
            f"{result.stderr.strip()}"
        )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("Approved baseline catalogue root must be an object")
    return value


def dossier_record_counts(audit: dict[str, Any]) -> Counter[str]:
    """Count source dossier records, without inferring unique people."""
    counts: Counter[str] = Counter()
    records = audit.get("records")
    if not isinstance(records, list):
        raise ValueError("diagnostic audit records must be a list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"diagnostic audit records[{index}] must be an object")
        desired = record.get("desired_tags")
        if not isinstance(desired, list):
            raise ValueError(
                f"diagnostic audit records[{index}].desired_tags must be a list"
            )
        ids = {
            item.get("id")
            for item in desired
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"].strip()
        }
        counts.update(ids)
    return counts


def prepare_migration(
    current: dict[str, Any],
    baseline: dict[str, Any],
    diagnostic_audit: dict[str, Any],
    *,
    baseline_ref: str,
    source_run: str,
    audit_reference: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if current.get("schema_version") != 1:
        raise ValueError("current catalogue must use pre-lifecycle schema_version 1")
    if baseline.get("schema_version") != 1:
        raise ValueError("approved baseline must use schema_version 1")
    current_tags = current.get("tags")
    baseline_tags = baseline.get("tags")
    if not isinstance(current_tags, list) or not isinstance(baseline_tags, list):
        raise ValueError("current and baseline catalogues must contain tags lists")

    baseline_by_id = {tag.get("id"): tag for tag in baseline_tags}
    current_by_id = {tag.get("id"): tag for tag in current_tags}
    missing_baseline_ids = sorted(set(baseline_by_id) - set(current_by_id))
    if missing_baseline_ids:
        raise ValueError(
            "current catalogue is missing approved baseline IDs: "
            + ", ".join(missing_baseline_ids)
        )

    counts = dossier_record_counts(diagnostic_audit)
    migrated_tags: list[dict[str, Any]] = []
    ambiguous_metadata: list[dict[str, Any]] = []
    lifecycle_counts: Counter[str] = Counter(
        {status: 0 for status in ("active", "candidate", "inactive", "merged")}
    )

    for current_tag in current_tags:
        tag_id = current_tag.get("id")
        if tag_id in baseline_by_id:
            baseline_tag = baseline_by_id[tag_id]
            migrated = deepcopy(baseline_tag)
            status = "merged" if baseline_tag.get("merged_into") else "active"
            lifecycle: dict[str, Any] = {
                "approval_basis": "approved_pre_run_baseline",
                "approval_ref": baseline_ref,
            }
            changed_fields = {
                key: {
                    "approved_value": deepcopy(baseline_tag.get(key)),
                    "post_run_value": deepcopy(current_tag.get(key)),
                }
                for key in sorted(set(baseline_tag) | set(current_tag))
                if baseline_tag.get(key) != current_tag.get(key)
            }
            if changed_fields:
                pending_aliases = sorted(
                    set(current_tag.get("aliases", []))
                    - set(baseline_tag.get("aliases", [])),
                    key=str.casefold,
                )
                if pending_aliases:
                    lifecycle["pending_aliases"] = pending_aliases
                lifecycle["post_run_metadata_review_required"] = True
                ambiguous_metadata.append(
                    {
                        "id": tag_id,
                        "name": baseline_tag.get("name"),
                        "changed_fields": changed_fields,
                        "migration_action": (
                            "Restored approved metadata; preserved added aliases "
                            "as non-resolving pending_aliases."
                        ),
                    }
                )
        else:
            migrated = deepcopy(current_tag)
            record_count = counts.get(str(tag_id), 0)
            if current_tag.get("merged_into") in baseline_by_id:
                status = "merged"
                lifecycle = {
                    "reason": "post_baseline_merge_to_approved_active_tag",
                    "source_run": source_run,
                    "dossier_record_count": record_count,
                }
            elif record_count == 1:
                status = "inactive"
                migrated["merged_into"] = None
                lifecycle = {
                    "reason": "runaway_generated_singleton_suppressed",
                    "source_run": source_run,
                    "dossier_record_count": record_count,
                }
            elif record_count >= 2:
                status = "candidate"
                migrated["merged_into"] = None
                lifecycle = {
                    "reason": "post_baseline_unapproved_frequency_candidate",
                    "source_run": source_run,
                    "dossier_record_count": record_count,
                }
            else:
                status = "inactive"
                prior_merge = migrated.get("merged_into")
                migrated["merged_into"] = None
                lifecycle = {
                    "reason": "post_baseline_generated_unreferenced",
                    "source_run": source_run,
                    "dossier_record_count": 0,
                }
                if prior_merge:
                    lifecycle["prior_merged_into"] = prior_merge
        migrated["status"] = status
        migrated["lifecycle"] = lifecycle
        migrated_tags.append(migrated)
        lifecycle_counts.update([status])

    updated = {
        "schema_version": 2,
        "dataset": current.get("dataset", "owner_tag_catalogue"),
        "description": (
            "Lifecycle-aware owner-tag registry. Production consumers expose "
            "only active tags and canonical redirects; candidates and inactive "
            "entries are preserved but are not assignable."
        ),
        "governance_policy": "docs/ai/OWNER_TAG_GOVERNANCE.md",
        "lifecycle_migration": {
            "approved_baseline_ref": baseline_ref,
            "source_run": source_run,
            "diagnostic_audit": audit_reference,
            "count_semantics": "source dossier records, not unique people",
        },
        "tags": migrated_tags,
    }
    TagCatalogue(updated)

    classified = sum(lifecycle_counts.values())
    report = {
        "schema_version": 1,
        "operation": "owner_tag_lifecycle_migration",
        "approved_baseline_ref": baseline_ref,
        "source_run": source_run,
        "diagnostic_audit": audit_reference,
        "diagnostic_limitations": [
            "The audit was offline and did not read live tag assignments.",
            "Counts describe source dossier records, not deduplicated people.",
            "Frequency informed lifecycle triage but did not approve any tag.",
        ],
        "baseline_active_tag_count": len(baseline_tags),
        "current_tag_count": len(current_tags),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "stable_ids_preserved": set(current_by_id) == {
            tag["id"] for tag in migrated_tags
        },
        "ambiguous_approval_case_count": len(ambiguous_metadata),
        "ambiguous_approval_cases": ambiguous_metadata,
        "unclassified_tag_count": len(current_tags) - classified,
        "dossier_record_count_scope": {
            "audit_record_count": len(diagnostic_audit.get("records", [])),
            "distinct_referenced_tag_count": len(counts),
        },
        "dossiers_modified": 0,
        "live_state_read": False,
        "live_state_modified": False,
    }
    return updated, report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate the runaway owner-tag catalogue into explicit lifecycle "
            "states. Dry-run is the default."
        )
    )
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_TAG_CATALOGUE_PATH)
    parser.add_argument("--baseline-ref", default=DEFAULT_BASELINE_REF)
    parser.add_argument("--baseline-file", type=Path)
    parser.add_argument("--source-run", default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--diagnostic-audit", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    catalogue_path = args.catalogue.resolve(strict=True)
    current = _load_object(catalogue_path)
    baseline = (
        _load_object(args.baseline_file.resolve(strict=True))
        if args.baseline_file is not None
        else _load_git_catalogue(args.baseline_ref, catalogue_path)
    )
    audit_path = args.diagnostic_audit.resolve(strict=True)
    audit = _load_object(audit_path)
    try:
        audit_reference = audit_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        audit_reference = audit_path.name
    updated, report = prepare_migration(
        current,
        baseline,
        audit,
        baseline_ref=args.baseline_ref,
        source_run=args.source_run,
        audit_reference=audit_reference,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Dry-run only; no catalogue or report was written.")
        return 0
    atomic_write_json(catalogue_path, updated)
    atomic_write_json(args.report, report)
    print(f"Migrated catalogue: {catalogue_path}")
    print(f"Migration report: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
