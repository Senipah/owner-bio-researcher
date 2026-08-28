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
        "--replace-tags",
        action="store_true",
        help=(
            "With --apply, also remove live tags absent from the dossier. "
            "Without this flag apply mode is add-only."
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if any(person_id <= 0 for person_id in (args.person_ids or [])):
        parser.error("--person-id must be a positive integer")

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
    except (OSError, ValueError) as exc:
        print(f"Could not prepare tag reconciliation: {exc}", file=sys.stderr)
        return 1

    if args.limit is not None:
        targets = targets[: args.limit]

    stamp = _stamp()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_dir / (
        f"owner-tag-update-{'apply' if args.apply else 'dry-run'}-{stamp}.json"
    )
    audit: dict[str, Any] = {
        "schema_version": 1,
        "started_at": utc_now(),
        "mode": "apply" if args.apply else "dry-run",
        "dossier_directory": str(dossier_directory),
        "tag_catalogue": catalogue.source_reference,
        "replace_tags": bool(args.replace_tags),
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
        atomic_write_json(audit_path, audit)
        print("No usable completed dossiers matched the selection.")
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
                    record["plan"] = plan
                    if plan["conflicts"]:
                        record["status"] = "conflict"
                        failures += 1
                        print("  Skipped because the tag state is ambiguous.")
                        continue
                    if not plan["has_changes"]:
                        record["status"] = "no_changes"
                        continue
                    if not args.apply:
                        record["status"] = "planned"
                        print(
                            f"  Planned: {len(plan['additions'])} additions, "
                            f"{len(plan['removals'])} removals."
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
    atomic_write_json(audit_path, audit)
    print(f"Audit report: {audit_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
