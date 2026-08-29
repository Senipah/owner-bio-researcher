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
from src.io_utils import atomic_write_json, utc_now
from src.owner_tags import fetch_owner_tags, load_tag_targets
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, load_tag_catalogue


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile live SYN owner tags against completed schema-v8 "
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
            "Build a no-login publication-eligibility manifest only. This "
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
        "--minimum-owner-count",
        "--min-owner-count",
        type=int,
        default=2,
        help=(
            "Only add a tag when at least this many usable completed dossiers "
            "contain it (default: 2). Existing matching live tags are retained."
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
    owner_counts: Counter[str],
    minimum_owner_count: int,
) -> dict[str, Any]:
    """Suppress new low-frequency tags without removing existing instances."""
    suppressed_additions = [
        {**item, "owner_count": owner_counts[item["id"]]}
        for item in plan["additions"]
        if owner_counts[item["id"]] < minimum_owner_count
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


def build_offline_publication_record(
    target: dict[str, Any],
    *,
    owner_counts: Counter[str],
    minimum_owner_count: int,
) -> dict[str, Any]:
    """Describe publishable dossier tags without reading or writing the website."""
    publishable = [
        {**item, "owner_count": owner_counts[item["id"]]}
        for item in target["desired_tags"]
        if owner_counts[item["id"]] >= minimum_owner_count
    ]
    suppressed = [
        {**item, "owner_count": owner_counts[item["id"]]}
        for item in target["desired_tags"]
        if owner_counts[item["id"]] < minimum_owner_count
    ]
    return {
        **target,
        "status": "offline_manifest",
        "live_comparison_performed": False,
        "operations": [],
        "plan": {
            "mode": "offline_publication_eligibility",
            "publishable_desired_tags": publishable,
            "suppressed_additions": suppressed,
            "additions": None,
            "removals": None,
            "conflicts": [],
            "note": (
                "No live state was read. Publishable tags meet the corpus "
                "threshold; suppressed additions are low-frequency desired "
                "tags that must not be newly published. Existing live "
                "singletons cannot be identified offline and should be "
                "retained by any later live reconciliation."
            ),
        },
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if any(person_id <= 0 for person_id in (args.person_ids or [])):
        parser.error("--person-id must be a positive integer")
    if args.minimum_owner_count < 1:
        parser.error("--minimum-owner-count must be a positive integer")
    if args.offline and args.apply:
        parser.error("--offline cannot be combined with --apply")
    if args.offline and args.replace_tags:
        parser.error("--offline cannot evaluate --replace-tags removals")

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
        owner_counts: Counter[str] = Counter(
            item["id"]
            for target in all_targets
            for item in target["desired_tags"]
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
        "schema_version": 1,
        "started_at": utc_now(),
        "mode": mode,
        "dossier_directory": str(dossier_directory),
        "tag_catalogue": catalogue.source_reference,
        "replace_tags": bool(args.replace_tags),
        "minimum_owner_count_for_additions": args.minimum_owner_count,
        "owner_count_scope": {
            "usable_completed_dossiers": len(all_targets),
            "distinct_tags": len(owner_counts),
        },
        "removals_authorized": bool(args.apply and args.replace_tags),
        "selected_person_ids": sorted(set(args.person_ids or [])),
        "target_count": len(targets),
        "skipped_count": len(skipped),
        "skipped_dossiers": skipped,
        "records": [],
    }
    atomic_write_json(audit_path, audit)

    if not targets:
        audit["finished_at"] = utc_now()
        audit["failure_count"] = 0
        audit["processed_count"] = 0
        audit["status_counts"] = {}
        audit["suppressed_addition_count"] = 0
        audit["suppressed_low_frequency_tags"] = []
        atomic_write_json(audit_path, audit)
        print("No usable completed dossiers matched the selection.")
        print(f"Audit report: {audit_path}")
        return 0

    if args.offline:
        audit["records"] = [
            build_offline_publication_record(
                target,
                owner_counts=owner_counts,
                minimum_owner_count=args.minimum_owner_count,
            )
            for target in targets
        ]
        suppressed = [
            item
            for record in audit["records"]
            for item in record["plan"]["suppressed_additions"]
        ]
        audit["finished_at"] = utc_now()
        audit["failure_count"] = 0
        audit["processed_count"] = len(audit["records"])
        audit["status_counts"] = {"offline_manifest": len(audit["records"])}
        audit["operation_counts"] = {}
        audit["live_read_performed"] = False
        audit["suppressed_addition_count"] = len(suppressed)
        audit["suppressed_low_frequency_tags"] = [
            {
                "id": tag_id,
                "name": next(
                    item["name"] for item in suppressed if item["id"] == tag_id
                ),
                "owner_count": owner_counts[tag_id],
                "suppressed_owner_count": count,
            }
            for tag_id, count in sorted(
                Counter(item["id"] for item in suppressed).items()
            )
        ]
        atomic_write_json(audit_path, audit)
        print(
            f"Offline manifest prepared for {len(audit['records'])} owners; "
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
                    "operations": [],
                }
                audit["records"].append(record)
                atomic_write_json(audit_path, audit)
                try:
                    live_tags = fetch_owner_tags(context.session, person_id)
                    plan = build_tag_change_plan(
                        person_id=person_id,
                        desired_names=desired_names,
                        live_tags=live_tags,
                        catalogue=catalogue,
                    )
                    suppress_low_frequency_additions(
                        plan,
                        owner_counts=owner_counts,
                        minimum_owner_count=args.minimum_owner_count,
                    )
                    record["plan"] = plan
                    if plan["conflicts"]:
                        record["status"] = "conflict"
                        failures += 1
                        print("  Skipped because the tag state is ambiguous.")
                        continue
                    if not plan["has_changes"]:
                        if plan["suppressed_additions"]:
                            record["status"] = (
                                "low_frequency_additions_suppressed"
                            )
                            print(
                                "  Suppressed "
                                f"{len(plan['suppressed_additions'])} additions "
                                "below the owner-count threshold."
                            )
                        else:
                            record["status"] = "no_changes"
                        continue
                    if not args.apply:
                        record["status"] = "planned"
                        print(
                            f"  Planned: {len(plan['additions'])} additions, "
                            f"{len(plan['removals'])} removals, "
                            f"{len(plan['suppressed_additions'])} "
                            "low-frequency additions suppressed."
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
                        owner_counts=owner_counts,
                        minimum_owner_count=args.minimum_owner_count,
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
    audit["suppressed_addition_count"] = len(suppressed)
    audit["suppressed_low_frequency_tags"] = [
        {
            "id": tag_id,
            "name": next(
                item["name"] for item in suppressed if item["id"] == tag_id
            ),
            "owner_count": owner_counts[tag_id],
            "suppressed_owner_count": count,
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
