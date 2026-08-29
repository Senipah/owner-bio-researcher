from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.auth import authenticated_context
from src.browser_update import OwnerBrowserUpdater
from src.constants import OWNER_DETAIL_URL
from src.diffing import build_tag_change_plan
from src.io_utils import atomic_write_json, load_json_unvalidated, utc_now
from src.owner_tags import fetch_owner_tags, load_tag_targets
from src.tag_diagnostics import build_tag_governance_diagnostics
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, load_tag_catalogue


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit or reconcile live SYN owner tags against completed schema-v8 "
            "research dossiers. Dry-run is the default."
        )
    )
    parser.add_argument("--dossier-dir", type=Path, required=True)
    parser.add_argument(
        "--tag-catalogue",
        type=Path,
        default=DEFAULT_TAG_CATALOGUE_PATH,
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply additions. Without this flag the command is read-only.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Build a no-login frequency and lifecycle audit only. This "
            "does not read live owner pages, so additions and removals cannot "
            "be reconciled against the website."
        ),
    )
    parser.add_argument(
        "--replace-tags",
        action="store_true",
        help=(
            "With --apply, also remove live tags absent from the dossier. "
            "Without this flag apply mode is add-only."
        ),
    )
    parser.add_argument(
        "--minimum-dossier-record-count",
        "--minimum-owner-count",
        "--min-owner-count",
        dest="minimum_dossier_record_count",
        type=int,
        default=2,
        help=(
            "Only add a tag when at least this many usable completed dossiers "
            "contain it (default: 2). This operational threshold does not "
            "approve a taxonomy concept. Existing matching live tags are retained."
        ),
    )
    parser.add_argument(
        "--reviewed-manifest",
        type=Path,
        help=(
            "Required with --apply --replace-tags. Supply a previously reviewed "
            "live dry-run audit; new or changed removals are blocked."
        ),
    )
    parser.add_argument(
        "--person-id",
        action="append",
        type=int,
        dest="person_ids",
        help="Only process this person ID; may be supplied more than once.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path("output/audits"),
    )
    return parser


def _verification_succeeded(
    plan: dict[str, Any],
    *,
    replace_tags: bool,
) -> bool:
    if plan["conflicts"] or plan["additions"]:
        return False
    return not replace_tags or not plan["removals"]


def suppress_low_frequency_additions(
    plan: dict[str, Any],
    *,
    dossier_record_counts: Counter[str],
    minimum_dossier_record_count: int,
) -> dict[str, Any]:
    """Suppress new low-frequency tags without removing existing instances."""
    suppressed_additions = [
        {
            **item,
            "dossier_record_count": dossier_record_counts[item["id"]],
        }
        for item in plan["additions"]
        if dossier_record_counts[item["id"]] < minimum_dossier_record_count
    ]
    suppressed_ids = {item["id"] for item in suppressed_additions}
    if not suppressed_ids:
        plan["suppressed_additions"] = []
        return plan

    suppressed_alias_associations = {
        item["from"]["association_id"]
        for item in plan["alias_replacements"]
        if item["to"]["id"] in suppressed_ids
    }
    plan["additions"] = [
        item for item in plan["additions"] if item["id"] not in suppressed_ids
    ]
    plan["removals"] = [
        item
        for item in plan["removals"]
        if item["association_id"] not in suppressed_alias_associations
    ]
    plan["alias_replacements"] = [
        item
        for item in plan["alias_replacements"]
        if item["to"]["id"] not in suppressed_ids
    ]
    plan["suppressed_additions"] = suppressed_additions
    plan["has_changes"] = bool(plan["additions"] or plan["removals"])
    plan["is_exact"] = not plan["has_changes"]
    return plan


def build_offline_review_record(
    target: dict[str, Any],
    *,
    dossier_record_counts: Counter[str],
    minimum_dossier_record_count: int,
) -> dict[str, Any]:
    """Describe active assignment frequency without inferring live changes."""
    frequency_eligible = [
        {
            **item,
            "dossier_record_count": dossier_record_counts[item["id"]],
        }
        for item in target["desired_tags"]
        if dossier_record_counts[item["id"]] >= minimum_dossier_record_count
    ]
    suppressed = [
        {
            **item,
            "dossier_record_count": dossier_record_counts[item["id"]],
        }
        for item in target["desired_tags"]
        if dossier_record_counts[item["id"]] < minimum_dossier_record_count
    ]
    return {
        **target,
        "status": "offline_manifest",
        "live_comparison_performed": False,
        "operations": [],
        "plan": {
            "mode": "offline_frequency_review",
            "frequency_eligible_active_assignments": frequency_eligible,
            "below_addition_threshold_assignments": suppressed,
            "additions": None,
            "removals": None,
            "conflicts": [],
            "note": (
                "No live state was read, so additions and removals are unknown. "
                "The frequency threshold is an operational review signal, not "
                "taxonomy approval. Existing live low-frequency assignments "
                "cannot be identified offline and must not be inferred."
            ),
        },
    }


def protect_non_production_target(
    plan: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any]:
    """Prevent incomplete legacy desired state from authorising removals."""
    if target.get("replacement_safe", True):
        plan["blocked_removals"] = []
        plan["blocked_alias_replacements"] = []
        return plan
    alias_target_ids = {
        item["to"]["id"] for item in plan.get("alias_replacements", [])
    }
    plan["blocked_removals"] = list(plan.get("removals", []))
    plan["blocked_alias_replacements"] = list(
        plan.get("alias_replacements", [])
    )
    plan["additions"] = [
        item for item in plan.get("additions", []) if item["id"] not in alias_target_ids
    ]
    plan["removals"] = []
    plan["alias_replacements"] = []
    plan["replacement_block_reason"] = (
        "The dossier contains candidate, inactive, unknown, mismatched, or "
        "duplicated legacy tag references. It may be audited, but it cannot "
        "authorise destructive reconciliation until corrected."
    )
    plan["has_changes"] = bool(plan["additions"])
    plan["is_exact"] = False
    return plan


def _removal_signature(item: dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("association_id", "")).strip(),
        str(item.get("name", "")).strip(),
    )


def load_reviewed_removal_manifest(
    path: Path,
    *,
    dossier_directory: Path,
    catalogue_source: str,
    minimum_dossier_record_count: int,
) -> dict[int, set[tuple[str, str]]]:
    """Load exact removals from a successful live dry-run audit."""
    document = load_json_unvalidated(path)
    if not isinstance(document, dict):
        raise ValueError("reviewed manifest root must be an object")
    if document.get("schema_version") != 2:
        raise ValueError("reviewed manifest must use owner-tag audit schema 2")
    if document.get("mode") != "dry-run":
        raise ValueError("reviewed manifest must be a live dry-run")
    if document.get("live_read_performed") is not True:
        raise ValueError("reviewed manifest did not complete a live read")
    if document.get("dossier_directory") != str(dossier_directory):
        raise ValueError("reviewed manifest dossier directory does not match")
    if document.get("tag_catalogue") != catalogue_source:
        raise ValueError("reviewed manifest tag catalogue does not match")
    if (
        document.get("minimum_dossier_record_count_for_new_additions")
        != minimum_dossier_record_count
    ):
        raise ValueError("reviewed manifest frequency threshold does not match")
    reviewed: dict[int, set[tuple[str, str]]] = {}
    for record in document.get("records", []):
        if not isinstance(record, dict):
            continue
        person_id = record.get("person_id")
        if not isinstance(person_id, int):
            continue
        if record.get("live_comparison_performed") is not True:
            continue
        plan = record.get("plan")
        if not isinstance(plan, dict):
            continue
        reviewed[person_id] = {
            _removal_signature(item)
            for item in plan.get("removals", [])
            if isinstance(item, dict)
        }
    return reviewed


def unreviewed_removals(
    plan: dict[str, Any],
    reviewed: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    return [
        item
        for item in plan.get("removals", [])
        if _removal_signature(item) not in reviewed
    ]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if any(person_id <= 0 for person_id in (args.person_ids or [])):
        parser.error("--person-id must be a positive integer")
    if args.minimum_dossier_record_count < 1:
        parser.error("--minimum-dossier-record-count must be a positive integer")
    if args.offline and args.apply:
        parser.error("--offline cannot be combined with --apply")
    if args.offline and args.replace_tags:
        parser.error("--offline cannot evaluate --replace-tags removals")
    if args.apply and args.replace_tags and args.reviewed_manifest is None:
        parser.error(
            "--apply --replace-tags requires --reviewed-manifest from a live dry-run"
        )
    if args.reviewed_manifest is not None and not (
        args.apply and args.replace_tags
    ):
        parser.error(
            "--reviewed-manifest is used only with --apply --replace-tags"
        )

    try:
        dossier_directory = args.dossier_dir.resolve(strict=True)
        if not dossier_directory.is_dir():
            raise ValueError(
                f"Dossier path is not a directory: {dossier_directory}"
            )
        catalogue = load_tag_catalogue(args.tag_catalogue.resolve(strict=True))
        targets, skipped = load_tag_targets(
            dossier_directory,
            catalogue,
            person_ids=set(args.person_ids or []),
        )
        all_targets, _ = load_tag_targets(dossier_directory, catalogue)
        dossier_record_counts: Counter[str] = Counter(
            item["id"]
            for target in all_targets
            for item in target["desired_tags"]
        )
        reviewed_removals = (
            load_reviewed_removal_manifest(
                args.reviewed_manifest.resolve(strict=True),
                dossier_directory=dossier_directory,
                catalogue_source=catalogue.source_reference,
                minimum_dossier_record_count=args.minimum_dossier_record_count,
            )
            if args.reviewed_manifest is not None
            else {}
        )
    except (OSError, ValueError) as exc:
        print(f"Could not prepare tag reconciliation: {exc}", file=sys.stderr)
        return 1

    if args.limit is not None:
        targets = targets[: args.limit]

    stamp = _stamp()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    mode = "offline-dry-run" if args.offline else (
        "apply" if args.apply else "dry-run"
    )
    audit_path = args.audit_dir / f"owner-tag-update-{mode}-{stamp}.json"
    audit: dict[str, Any] = {
        "schema_version": 2,
        "started_at": utc_now(),
        "mode": mode,
        "dossier_directory": str(dossier_directory),
        "tag_catalogue": catalogue.source_reference,
        "replace_tags": bool(args.replace_tags),
        "minimum_dossier_record_count_for_new_additions": (
            args.minimum_dossier_record_count
        ),
        "dossier_record_count_scope": {
            "usable_completed_dossier_records": len(all_targets),
            "distinct_active_tags": len(dossier_record_counts),
            "count_semantics": "source dossier records, not unique people",
        },
        "removals_authorized": bool(
            args.apply and args.replace_tags and args.reviewed_manifest
        ),
        "reviewed_manifest": (
            str(args.reviewed_manifest.resolve())
            if args.reviewed_manifest is not None
            else None
        ),
        "selected_person_ids": sorted(set(args.person_ids or [])),
        "target_count": len(targets),
        "skipped_count": len(skipped),
        "skipped_dossiers": skipped,
        "production_ready_target_count": sum(
            bool(target.get("production_ready")) for target in targets
        ),
        "non_active_reference_count": sum(
            len(target.get("non_active_tag_references", []))
            for target in targets
        ),
        "governance_diagnostics": build_tag_governance_diagnostics(
            all_targets,
            catalogue,
        ),
        "live_read_performed": False,
        "records": [],
    }
    atomic_write_json(audit_path, audit)

    if not targets:
        audit["finished_at"] = utc_now()
        audit["failure_count"] = 0
        audit["processed_count"] = 0
        audit["status_counts"] = {}
        audit["below_threshold_addition_count"] = 0
        audit["below_threshold_tags"] = []
        atomic_write_json(audit_path, audit)
        print("No usable completed dossiers matched the selection.")
        print(f"Audit report: {audit_path}")
        return 0

    if args.offline:
        audit["records"] = [
            build_offline_review_record(
                target,
                dossier_record_counts=dossier_record_counts,
                minimum_dossier_record_count=args.minimum_dossier_record_count,
            )
            for target in targets
        ]
        suppressed = [
            item
            for record in audit["records"]
            for item in record["plan"]["below_addition_threshold_assignments"]
        ]
        audit["finished_at"] = utc_now()
        audit["failure_count"] = 0
        audit["processed_count"] = len(audit["records"])
        audit["status_counts"] = {"offline_manifest": len(audit["records"])}
        audit["operation_counts"] = {}
        audit["live_read_performed"] = False
        audit["below_threshold_addition_count"] = len(suppressed)
        audit["below_threshold_tags"] = [
            {
                "id": tag_id,
                "name": next(
                    item["name"] for item in suppressed if item["id"] == tag_id
                ),
                "dossier_record_count": dossier_record_counts[tag_id],
                "affected_dossier_record_count": count,
            }
            for tag_id, count in sorted(
                Counter(item["id"] for item in suppressed).items()
            )
        ]
        atomic_write_json(audit_path, audit)
        print(
            f"Offline lifecycle audit prepared for {len(audit['records'])} "
            "dossier records; "
            "no login or live website read was performed."
        )
        print(f"Audit report: {audit_path}")
        return 0

    failures = 0
    try:
        with authenticated_context(headless=args.headless) as context:
            updater = OwnerBrowserUpdater(context.driver)
            for index, target in enumerate(targets, start=1):
                person_id = target["person_id"]
                desired_names = [
                    item["name"] for item in target["desired_tags"]
                ]
                print(
                    f"[{index}/{len(targets)}] Checking owner {person_id} "
                    f"({target['display_name']})..."
                )
                record: dict[str, Any] = {
                    **target,
                    "status": "pending",
                    "live_comparison_performed": False,
                    "operations": [],
                }
                audit["records"].append(record)
                atomic_write_json(audit_path, audit)
                try:
                    live_tags = fetch_owner_tags(context.session, person_id)
                    record["live_comparison_performed"] = True
                    audit["live_read_performed"] = True
                    plan = build_tag_change_plan(
                        person_id=person_id,
                        desired_names=desired_names,
                        live_tags=live_tags,
                        catalogue=catalogue,
                    )
                    protect_non_production_target(plan, target)
                    suppress_low_frequency_additions(
                        plan,
                        dossier_record_counts=dossier_record_counts,
                        minimum_dossier_record_count=(
                            args.minimum_dossier_record_count
                        ),
                    )
                    record["plan"] = plan
                    if plan["conflicts"]:
                        record["status"] = "conflict"
                        failures += 1
                        print("  Skipped because the tag state is ambiguous.")
                        continue
                    if args.apply and not target.get("production_ready", True):
                        record["status"] = "blocked_non_active_references"
                        failures += 1
                        print(
                            "  Blocked: dossier contains non-active or unresolved "
                            "tag references."
                        )
                        continue
                    if not plan["has_changes"]:
                        if plan["suppressed_additions"]:
                            record["status"] = (
                                "below_threshold_additions_suppressed"
                            )
                            print(
                                "  Suppressed "
                                f"{len(plan['suppressed_additions'])} additions "
                                "below the dossier-record threshold."
                            )
                        elif not target.get("production_ready", True):
                            record["status"] = "blocked_non_active_references"
                        else:
                            record["status"] = "no_changes"
                        continue
                    if not args.apply:
                        record["status"] = "planned"
                        print(
                            f"  Planned: {len(plan['additions'])} additions, "
                            f"{len(plan['removals'])} removals, "
                            f"{len(plan['suppressed_additions'])} "
                            "below-threshold additions suppressed."
                        )
                        continue

                    if args.replace_tags:
                        unreviewed = unreviewed_removals(
                            plan,
                            reviewed_removals.get(person_id, set()),
                        )
                        if unreviewed:
                            record["unreviewed_removals"] = unreviewed
                            record["status"] = "blocked_unreviewed_removals"
                            failures += 1
                            print(
                                "  Blocked: current removals differ from the "
                                "reviewed live dry-run manifest."
                            )
                            continue

                    removals = plan["removals"] if args.replace_tags else []
                    if not plan["additions"] and not removals:
                        record["status"] = "removals_suppressed"
                        print(
                            "  No additions; removals require --replace-tags."
                        )
                        continue

                    def checkpoint(operation: dict[str, Any]) -> None:
                        record["operations"].append(
                            {**operation, "completed_at": utc_now()}
                        )
                        audit["updated_at"] = utc_now()
                        atomic_write_json(audit_path, audit)

                    updater.update_tags(
                        profile_url=OWNER_DETAIL_URL.format(person_id=person_id),
                        expected_live=plan["live_tags"],
                        additions=plan["additions"],
                        removals=removals,
                        on_operation=checkpoint,
                    )
                    live_after = fetch_owner_tags(context.session, person_id)
                    record["live_after"] = live_after
                    verification = build_tag_change_plan(
                        person_id=person_id,
                        desired_names=desired_names,
                        live_tags=live_after,
                        catalogue=catalogue,
                    )
                    suppress_low_frequency_additions(
                        verification,
                        dossier_record_counts=dossier_record_counts,
                        minimum_dossier_record_count=(
                            args.minimum_dossier_record_count
                        ),
                    )
                    record["verification"] = verification
                    if not _verification_succeeded(
                        verification,
                        replace_tags=args.replace_tags,
                    ):
                        raise RuntimeError(
                            "Live tags did not match the requested reconciliation"
                        )
                    if verification["removals"]:
                        record["status"] = (
                            "additions_applied_removals_suppressed"
                        )
                    else:
                        record["status"] = "applied_and_verified"
                except Exception as exc:
                    failures += 1
                    record["status"] = "error"
                    record["error"] = str(exc)
                    try:
                        record["live_after_error"] = fetch_owner_tags(
                            context.session,
                            person_id,
                        )
                    except Exception as refresh_exc:
                        record["live_after_error_failure"] = str(refresh_exc)
                    print(f"  Failed: {exc}", file=sys.stderr)
                finally:
                    audit["updated_at"] = utc_now()
                    atomic_write_json(audit_path, audit)
    except Exception as exc:
        failures += 1
        audit["fatal_error"] = str(exc)
        print(f"Tag update run stopped: {exc}", file=sys.stderr)

    audit["finished_at"] = utc_now()
    audit["failure_count"] = failures
    audit["processed_count"] = len(audit["records"])
    audit["status_counts"] = dict(
        sorted(Counter(record["status"] for record in audit["records"]).items())
    )
    audit["operation_counts"] = dict(
        sorted(
            Counter(
                operation["action"]
                for record in audit["records"]
                for operation in record["operations"]
            ).items()
        )
    )
    suppressed = [
        item
        for record in audit["records"]
        for item in record.get("plan", {}).get("suppressed_additions", [])
    ]
    audit["successful_live_read_count"] = sum(
        record.get("live_comparison_performed") is True
        for record in audit["records"]
    )
    audit["below_threshold_addition_count"] = len(suppressed)
    audit["below_threshold_tags"] = [
        {
            "id": tag_id,
            "name": next(
                item["name"] for item in suppressed if item["id"] == tag_id
            ),
            "dossier_record_count": dossier_record_counts[tag_id],
            "affected_dossier_record_count": count,
        }
        for tag_id, count in sorted(
            Counter(item["id"] for item in suppressed).items()
        )
    ]
    atomic_write_json(audit_path, audit)
    print(f"Audit report: {audit_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
