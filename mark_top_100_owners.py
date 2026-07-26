from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.auth import authenticated_context, fetch_html
from src.io_utils import (
    atomic_write_json,
    derived_output_path,
    load_json,
    load_json_unvalidated,
    utc_now,
)
from src.top_100 import (
    VesselOwnershipScanner,
    new_top_100_document,
    parse_top_100_list,
    top_100_page_url,
    validate_top_100_document,
)
from src.workflow import (
    annotate_top_100_owners,
    ensure_document_workflow,
    reset_top_100_annotations,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export YB Top-100 vessels and mark current owners in an owner export."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--owners-output",
        type=Path,
        help="Annotated owner output (default: INPUT.top-100.json)",
    )
    parser.add_argument(
        "--vessels-output",
        type=Path,
        default=Path("output/top-100-vessels.json"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--resume",
        action="store_true",
        help="Resume pending/error vessels from both existing output files.",
    )
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Re-export the vessel list and re-scan every vessel.",
    )
    parser.add_argument(
        "--limit-vessels",
        type=int,
        help="Scan at most this many eligible vessels; intended for smoke tests.",
    )
    parser.add_argument("--headless", action="store_true")
    return parser


def _export_vessel_list(
    session,
    output: Path,
    document: dict[str, Any],
) -> dict[str, Any]:
    seen_pages: set[int] = set()
    seen_vessels: set[int] = set()
    page = 1

    while page not in seen_pages:
        seen_pages.add(page)
        page_url = top_100_page_url(page)
        print(f"Exporting Top-100 vessel page {page}...")
        html = fetch_html(
            session,
            page_url,
            expected_marker="yb-fleet-vessel",
        )
        vessels, next_page, reported_last = parse_top_100_list(
            html,
            page_url=page_url,
            rank_offset=len(document["vessels"]),
        )
        for vessel in vessels:
            vessel_id = vessel["vessel_id"]
            if vessel_id in seen_vessels:
                document["source"]["warnings"].append(
                    f"Duplicate vessel_id {vessel_id} skipped on page {page}"
                )
                continue
            seen_vessels.add(vessel_id)
            document["vessels"].append(vessel)

        document["exported_at"] = utc_now()
        document["source"]["pages_exported"] = len(seen_pages)
        document["source"]["reported_last_page"] = reported_last
        document["source"]["vessel_count"] = len(document["vessels"])
        atomic_write_json(output, document)
        if next_page is None:
            break
        page = next_page
    else:
        raise RuntimeError(f"Top-100 pagination loop detected at page {page}")

    validate_top_100_document(document)
    return document


def _checkpoint(
    *,
    owner_document: dict[str, Any],
    vessel_document: dict[str, Any],
    owners_output: Path,
    vessels_output: Path,
) -> list[int]:
    unmatched = annotate_top_100_owners(
        owner_document, vessel_document["vessels"]
    )
    source = vessel_document["source"]
    source["unmatched_owner_ids"] = unmatched
    source["scan_error_count"] = sum(
        vessel.get("ownership_scan", {}).get("status") == "error"
        for vessel in vessel_document["vessels"]
    )
    vessel_document["updated_at"] = utc_now()
    atomic_write_json(vessels_output, vessel_document)
    atomic_write_json(owners_output, owner_document)
    return unmatched


def main() -> int:
    args = build_parser().parse_args()
    if args.limit_vessels is not None and args.limit_vessels <= 0:
        print("--limit-vessels must be a positive integer", file=sys.stderr)
        return 2

    owners_output = args.owners_output or derived_output_path(
        args.input, ".top-100"
    )
    input_resolved = args.input.resolve()
    owners_resolved = owners_output.resolve()
    vessels_resolved = args.vessels_output.resolve()
    if input_resolved in {owners_resolved, vessels_resolved}:
        print("Outputs must not overwrite the input file", file=sys.stderr)
        return 2
    if owners_resolved == vessels_resolved:
        print("Owner and vessel outputs must be different files", file=sys.stderr)
        return 2

    try:
        if args.resume:
            if not owners_output.exists() or not args.vessels_output.exists():
                raise FileNotFoundError(
                    "--resume requires both existing output files"
                )
            owner_document = load_json(owners_output)
            vessel_document = load_json_unvalidated(args.vessels_output)
            validate_top_100_document(vessel_document)
            ensure_document_workflow(owner_document)
        else:
            owner_document = deepcopy(load_json(args.input))
            ensure_document_workflow(owner_document)
            reset_top_100_annotations(owner_document)
            vessel_document = new_top_100_document()
    except Exception as exc:
        print(f"Could not prepare Top-100 outputs: {exc}", file=sys.stderr)
        return 1

    failures = 0
    try:
        with authenticated_context(headless=args.headless) as context:
            if not args.resume:
                vessel_document = _export_vessel_list(
                    context.session,
                    args.vessels_output,
                    vessel_document,
                )
                _checkpoint(
                    owner_document=owner_document,
                    vessel_document=vessel_document,
                    owners_output=owners_output,
                    vessels_output=args.vessels_output,
                )

            eligible = [
                vessel
                for vessel in vessel_document["vessels"]
                if args.refresh
                or vessel.get("ownership_scan", {}).get("status") != "ok"
            ]
            if args.refresh:
                for vessel in eligible:
                    vessel["edit_url"] = None
                    vessel["ubo_relationships"] = []
                    vessel["ownership_scan"] = {
                        "status": "pending",
                        "scanned_at": None,
                        "error": None,
                    }
            if args.limit_vessels is not None:
                eligible = eligible[: args.limit_vessels]

            scanner = VesselOwnershipScanner(context.driver)
            for index, vessel in enumerate(eligible, start=1):
                print(
                    f"[{index}/{len(eligible)}] Scanning rank "
                    f"{vessel['rank']} {vessel['vessel_name']}..."
                )
                try:
                    edit_url, relationships = scanner.scan(vessel)
                    vessel["edit_url"] = edit_url
                    vessel["ubo_relationships"] = relationships
                    vessel["ownership_scan"] = {
                        "status": "ok",
                        "scanned_at": utc_now(),
                        "error": None,
                    }
                except Exception as exc:
                    failures += 1
                    vessel["ownership_scan"] = {
                        "status": "error",
                        "scanned_at": utc_now(),
                        "error": str(exc),
                    }
                    print(f"  Failed: {exc}", file=sys.stderr)
                _checkpoint(
                    owner_document=owner_document,
                    vessel_document=vessel_document,
                    owners_output=owners_output,
                    vessels_output=args.vessels_output,
                )
    except Exception as exc:
        failures += 1
        print(f"Top-100 scan stopped: {exc}", file=sys.stderr)

    unmatched = _checkpoint(
        owner_document=owner_document,
        vessel_document=vessel_document,
        owners_output=owners_output,
        vessels_output=args.vessels_output,
    )
    vessel_count = len(vessel_document["vessels"])
    limited_run = args.limit_vessels is not None
    if not limited_run and vessel_count != 100:
        failures += 1
        warning = f"Expected 100 unique vessels, exported {vessel_count}"
        if warning not in vessel_document["source"]["warnings"]:
            vessel_document["source"]["warnings"].append(warning)
    if unmatched:
        failures += 1
        warning = (
            f"{len(unmatched)} owner person IDs were not present in the owner input"
        )
        if warning not in vessel_document["source"]["warnings"]:
            vessel_document["source"]["warnings"].append(warning)
    _checkpoint(
        owner_document=owner_document,
        vessel_document=vessel_document,
        owners_output=owners_output,
        vessels_output=args.vessels_output,
    )

    current_count = sum(
        owner["workflow"]["is_top_100_owner"]
        for owner in owner_document["owners"]
    )
    print(f"Top-100 vessels: {vessel_count}")
    print(f"Current Top-100 owners matched: {current_count}")
    print(f"Annotated owners: {owners_output}")
    print(f"Vessel dataset: {args.vessels_output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
