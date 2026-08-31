from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.auth import authenticated_context
from src.browser_update import OwnerBrowserUpdater
from src.constants import BIOGRAPHY_DETAIL_FIELDS
from src.diffing import build_owner_change_plan
from src.enrichment import (
    fetch_owner_details,
    fetch_owner_enrichment,
    refreshed_owner,
)
from src.io_utils import (
    atomic_write_json,
    load_json,
    load_json_unvalidated,
    utc_now,
)
from src.workflow import (
    ensure_document_workflow,
    mark_owner_updated_in_system,
    owner_matches_workflow,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_BIOGRAPHY_IGNORE_LIST = (
    PROJECT_ROOT / "config" / "biography-update-ignore-ids.json"
)


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely apply edited enriched owner JSON to SYN."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save changes. Without this flag the command is a dry run.",
    )
    parser.add_argument(
        "--allow-clear",
        action="store_true",
        help="Allow blank desired values to clear live details fields.",
    )
    parser.add_argument(
        "--replace-socials",
        action="store_true",
        help="Make live social profiles exactly match JSON, including removals.",
    )
    parser.add_argument(
        "--detail-field",
        action="append",
        dest="detail_fields",
        help=(
            "Only reconcile this named details field; may be supplied more "
            "than once. When used, social profiles are not changed."
        ),
    )
    parser.add_argument(
        "--biography-ignore-list",
        type=Path,
        default=DEFAULT_BIOGRAPHY_IGNORE_LIST,
        help=(
            "JSON config containing person_ids whose biography and "
            "long_biography fields must not be written."
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
    parser.add_argument(
        "--top-100-only",
        action="store_true",
        help="Only process owners currently linked to a Top-100 vessel.",
    )
    parser.add_argument(
        "--ai-enriched-only",
        action="store_true",
        help="Only process records marked as AI enriched.",
    )
    parser.add_argument(
        "--not-updated-only",
        action="store_true",
        help="Only process records not yet marked updated in the system.",
    )
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=Path("output/audits"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Post-apply refreshed JSON path.",
    )
    return parser


def load_biography_ignore_ids(path: str | Path) -> set[int]:
    document = load_json_unvalidated(path)
    if not isinstance(document, dict):
        raise ValueError("ignore-list JSON must be an object")
    if document.get("schema_version") != 1:
        raise ValueError("ignore-list schema_version must be 1")
    person_ids = document.get("person_ids")
    if not isinstance(person_ids, list):
        raise ValueError("ignore-list person_ids must be an array")

    invalid_ids = [
        person_id
        for person_id in person_ids
        if type(person_id) is not int or person_id <= 0
    ]
    if invalid_ids:
        raise ValueError(
            "ignore-list person_ids must contain only positive integers"
        )
    if len(person_ids) != len(set(person_ids)):
        raise ValueError("ignore-list person_ids must not contain duplicates")
    return set(person_ids)


def _verify_plan(
    owner: dict[str, Any],
    *,
    details: dict[str, Any],
    socials: list[dict[str, Any]],
    allow_clear: bool,
    replace_socials: bool,
    detail_fields: list[str] | None,
    ignore_biographies: bool,
) -> dict[str, Any]:
    return build_owner_change_plan(
        owner,
        live_details=details,
        live_socials=socials,
        allow_clear=allow_clear,
        replace_socials=replace_socials,
        detail_fields=detail_fields,
        ignored_detail_fields=(
            BIOGRAPHY_DETAIL_FIELDS if ignore_biographies else None
        ),
        include_socials=not detail_fields,
    )


def main() -> int:
    args = build_parser().parse_args()
    try:
        document = load_json(args.input)
    except Exception as exc:
        print(f"Could not load owner data: {exc}", file=sys.stderr)
        return 1
    try:
        biography_ignore_ids = load_biography_ignore_ids(
            args.biography_ignore_list
        )
    except Exception as exc:
        print(f"Could not load biography ignore list: {exc}", file=sys.stderr)
        return 1

    ensure_document_workflow(document)
    selected_ids = set(args.person_ids or [])
    owners = [
        owner
        for owner in document["owners"]
        if not selected_ids or owner["person_id"] in selected_ids
        if owner_matches_workflow(
            owner,
            top_100_only=args.top_100_only,
            ai_enriched_only=args.ai_enriched_only,
            not_updated_only=args.not_updated_only,
        )
    ]
    if args.limit is not None:
        owners = owners[: args.limit]
    if not owners:
        print("No owners matched the selection.")
        return 0
    protected_selected_ids = sorted(
        owner["person_id"]
        for owner in owners
        if owner["person_id"] in biography_ignore_ids
    )
    if protected_selected_ids:
        protected_text = ", ".join(map(str, protected_selected_ids))
        print(f"Biography overwrite protection active for: {protected_text}")

    stamp = _stamp()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_dir / (
        f"owner-update-{'apply' if args.apply else 'dry-run'}-{stamp}.json"
    )
    refreshed_document = deepcopy(document)
    refreshed_by_id = {
        owner["person_id"]: owner for owner in refreshed_document["owners"]
    }
    audit: dict[str, Any] = {
        "started_at": utc_now(),
        "mode": "apply" if args.apply else "dry-run",
        "input": str(args.input),
        "allow_clear": args.allow_clear,
        "replace_socials": args.replace_socials,
        "detail_fields": sorted(set(args.detail_fields or [])),
        "biography_ignore_list": str(args.biography_ignore_list),
        "biography_ignored_person_ids": sorted(biography_ignore_ids),
        "records": [],
    }
    failures = 0

    try:
        with authenticated_context(headless=args.headless) as context:
            updater = OwnerBrowserUpdater(context.driver)
            for index, owner in enumerate(owners, start=1):
                person_id = owner["person_id"]
                print(f"[{index}/{len(owners)}] Checking owner {person_id}...")
                record: dict[str, Any] = {
                    "person_id": person_id,
                    "status": "pending",
                }
                audit["records"].append(record)
                try:
                    ignore_biographies = person_id in biography_ignore_ids
                    record["biography_overwrite_protected"] = (
                        ignore_biographies
                    )
                    if args.detail_fields:
                        live_details = fetch_owner_details(
                            context.session,
                            person_id,
                        )
                        live_socials = deepcopy(
                            owner.get("_baseline", {}).get(
                                "social_media_profiles",
                                [],
                            )
                        )
                        type_lookup: dict[str, str] = {}
                    else:
                        live_details, live_socials, type_lookup = (
                            fetch_owner_enrichment(
                                context.session,
                                person_id,
                            )
                        )
                    plan = _verify_plan(
                        owner,
                        details=live_details,
                        socials=live_socials,
                        allow_clear=args.allow_clear,
                        replace_socials=args.replace_socials,
                        detail_fields=args.detail_fields,
                        ignore_biographies=ignore_biographies,
                    )
                    record["plan"] = plan
                    if plan["conflicts"]:
                        record["status"] = "conflict"
                        failures += 1
                        print("  Skipped because live data changed since export.")
                        continue
                    if not plan["has_changes"]:
                        record["status"] = "no_changes"
                        if args.apply:
                            refreshed_by_id[person_id].clear()
                            refreshed_by_id[person_id].update(
                                refreshed_owner(
                                    owner,
                                    details=live_details,
                                    socials=live_socials,
                                )
                            )
                            refreshed_document.setdefault(
                                "lookups", {}
                            ).setdefault("social_media_types", {}).update(
                                type_lookup
                            )
                            record["status"] = "current_and_refreshed"
                        continue
                    if not args.apply:
                        record["status"] = "planned"
                        continue

                    if plan["detail_changes"]:
                        updater.update_details(
                            profile_url=owner["profile_url"],
                            changes=plan["detail_changes"],
                        )
                    if (
                        plan["social_additions"]
                        or plan["social_replacements"]
                        or plan["social_removals"]
                    ):
                        updater.update_socials(
                            profile_url=owner["profile_url"],
                            additions=plan["social_additions"],
                            replacements=plan["social_replacements"],
                            removals=plan["social_removals"],
                        )

                    if args.detail_fields:
                        after_details = fetch_owner_details(
                            context.session,
                            person_id,
                        )
                        after_socials = live_socials
                        after_lookup: dict[str, str] = {}
                    else:
                        after_details, after_socials, after_lookup = (
                            fetch_owner_enrichment(
                                context.session,
                                person_id,
                            )
                        )
                    verification = _verify_plan(
                        owner,
                        details=after_details,
                        socials=after_socials,
                        allow_clear=args.allow_clear,
                        replace_socials=args.replace_socials,
                        detail_fields=args.detail_fields,
                        ignore_biographies=ignore_biographies,
                    )
                    record["verification"] = verification
                    if verification["conflicts"] or verification["has_changes"]:
                        raise RuntimeError(
                            "Saved values did not match the requested update"
                        )
                    record["status"] = "applied_and_verified"
                    refreshed_by_id[person_id].clear()
                    refreshed = refreshed_owner(
                        owner,
                        details=after_details,
                        socials=after_socials,
                    )
                    if not args.detail_fields:
                        mark_owner_updated_in_system(refreshed)
                    refreshed_by_id[person_id].update(refreshed)
                    refreshed_document.setdefault("lookups", {}).setdefault(
                        "social_media_types", {}
                    ).update(type_lookup)
                    refreshed_document["lookups"]["social_media_types"].update(
                        after_lookup
                    )
                except Exception as exc:
                    failures += 1
                    record["status"] = "error"
                    record["error"] = str(exc)
                    print(f"  Failed: {exc}", file=sys.stderr)
                finally:
                    audit["updated_at"] = utc_now()
                    atomic_write_json(audit_path, audit)
    except Exception as exc:
        failures += 1
        audit["fatal_error"] = str(exc)
        print(f"Update run stopped: {exc}", file=sys.stderr)

    audit["finished_at"] = utc_now()
    audit["failure_count"] = failures
    atomic_write_json(audit_path, audit)

    if args.apply:
        output = args.output or args.input.with_name(
            f"{args.input.stem}.applied-{stamp}.json"
        )
        refreshed_document["synchronized_at"] = utc_now()
        atomic_write_json(output, refreshed_document)
        print(f"Refreshed post-apply data: {output}")
    print(f"Audit report: {audit_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
