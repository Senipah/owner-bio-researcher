from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import requests

from src.auth import authenticated_context
from src.io_utils import (
    atomic_write_json,
    derived_output_path,
    load_json,
    utc_now,
)
from src.owner_vessels import (
    apply_owner_vessel_ranking,
    clone_session,
    current_vessel_references,
    fetch_owner_vessel_relationships,
    fetch_vessel_specification,
    sort_and_rank_owners,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich owners with current vessel relationships and normalized "
            "LOA, then sort owners by their largest known current vessel."
        )
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path (default: INPUT.vessel-enriched.json)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume successful owner and vessel scans from an existing output.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch selected owner pages and their current vessel specs.",
    )
    parser.add_argument(
        "--person-id",
        action="append",
        type=int,
        dest="person_ids",
        help="Only scan this person ID; may be supplied more than once.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of selected owner pages to scan.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent HTTP workers (default: 4; maximum: 16).",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
        help="Checkpoint after this many completed requests (default: 10).",
    )
    parser.add_argument("--headless", action="store_true")
    return parser


def _session_getter(
    source: requests.Session,
) -> Callable[[], requests.Session]:
    local = threading.local()

    def get_session() -> requests.Session:
        session = getattr(local, "session", None)
        if session is None:
            session = clone_session(source)
            local.session = session
        return session

    return get_session


def _checkpoint_if_due(
    completed: int,
    *,
    every: int,
    output: Path,
    document: dict[str, Any],
) -> None:
    if completed % every == 0:
        atomic_write_json(output, document)


def _scan_owners(
    *,
    document: dict[str, Any],
    owners: list[dict[str, Any]],
    session_getter: Callable[[], requests.Session],
    workers: int,
    checkpoint_every: int,
    output: Path,
) -> int:
    errors = 0

    def scan(owner: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
        relationships = fetch_owner_vessel_relationships(
            session_getter(), owner
        )
        return int(owner["person_id"]), relationships

    owners_by_id = {int(owner["person_id"]): owner for owner in owners}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scan, owner): owner for owner in owners}
        for completed, future in enumerate(as_completed(futures), start=1):
            source_owner = futures[future]
            person_id = int(source_owner["person_id"])
            owner = owners_by_id[person_id]
            try:
                _, relationships = future.result()
                owner["vessel_ownership"] = {
                    "status": "ok",
                    "scanned_at": utc_now(),
                    "error": None,
                    "relationships": relationships,
                    "current_vessels": [],
                    "largest_known_current_vessel": None,
                    "ranking_status": "pending",
                    "largest_current_loa_m": None,
                    "largest_current_gross_tonnage": None,
                    "loa_rank": None,
                }
                print(
                    f"[owner {completed}/{len(owners)}] {person_id}: "
                    f"{len(relationships)} relationship(s)"
                )
            except Exception as exc:
                errors += 1
                owner["vessel_ownership"] = {
                    "status": "error",
                    "scanned_at": utc_now(),
                    "error": str(exc),
                    "relationships": [],
                    "current_vessels": [],
                    "largest_known_current_vessel": None,
                    "ranking_status": "error",
                    "largest_current_loa_m": None,
                    "largest_current_gross_tonnage": None,
                    "loa_rank": None,
                }
                print(
                    f"[owner {completed}/{len(owners)}] {person_id}: {exc}",
                    file=sys.stderr,
                )
            _checkpoint_if_due(
                completed,
                every=checkpoint_every,
                output=output,
                document=document,
            )
    atomic_write_json(output, document)
    return errors


def _scan_vessels(
    *,
    document: dict[str, Any],
    vessels: list[dict[str, Any]],
    session_getter: Callable[[], requests.Session],
    workers: int,
    checkpoint_every: int,
    output: Path,
) -> int:
    errors = 0
    vessel_specs = document.setdefault("vessel_specifications", {})

    def scan(vessel: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        vessel_id = int(vessel["vessel_id"])
        result = fetch_vessel_specification(
            session_getter(),
            vessel_id=vessel_id,
            vessel_name=str(vessel.get("vessel_name", "")),
            specification_url=str(vessel["specification_url"]),
        )
        return vessel_id, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scan, vessel): vessel for vessel in vessels}
        for completed, future in enumerate(as_completed(futures), start=1):
            vessel = futures[future]
            vessel_id = int(vessel["vessel_id"])
            try:
                _, result = future.result()
                vessel_specs[str(vessel_id)] = result
                if result["status"] != "ok":
                    errors += 1
                    print(
                        f"[vessel {completed}/{len(vessels)}] {vessel_id}: "
                        f"{result['error']}",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[vessel {completed}/{len(vessels)}] {vessel_id}: "
                        f"{result['loa_raw']} -> {result['loa_m']}m"
                    )
            except Exception as exc:
                errors += 1
                vessel_specs[str(vessel_id)] = {
                    **vessel,
                    "status": "error",
                    "fetched_at": utc_now(),
                    "loa_raw": "",
                    "loa_m": None,
                    "gross_tonnage_raw": "",
                    "gross_tonnage": None,
                    "error": str(exc),
                }
                print(
                    f"[vessel {completed}/{len(vessels)}] {vessel_id}: {exc}",
                    file=sys.stderr,
                )
            _checkpoint_if_due(
                completed,
                every=checkpoint_every,
                output=output,
                document=document,
            )
    atomic_write_json(output, document)
    return errors


def main() -> int:
    args = build_parser().parse_args()
    if args.workers < 1 or args.workers > 16:
        print("--workers must be between 1 and 16", file=sys.stderr)
        return 2
    if args.checkpoint_every < 1:
        print("--checkpoint-every must be at least 1", file=sys.stderr)
        return 2

    output = args.output or derived_output_path(args.input, ".vessel-enriched")
    if output.resolve() == args.input.resolve():
        print("Output must differ from input", file=sys.stderr)
        return 2

    try:
        if args.resume and output.exists():
            document = load_json(output)
        else:
            document = deepcopy(load_json(args.input))
    except Exception as exc:
        print(f"Could not load owner data: {exc}", file=sys.stderr)
        return 1

    selected_ids = set(args.person_ids or [])
    eligible = [
        owner
        for owner in document["owners"]
        if (not selected_ids or owner["person_id"] in selected_ids)
        and (
            args.refresh
            or owner.get("vessel_ownership", {}).get("status") != "ok"
        )
    ]
    if args.limit is not None:
        eligible = eligible[: args.limit]

    errors = 0
    try:
        with authenticated_context(headless=args.headless) as context:
            session_getter = _session_getter(context.session)
            if eligible:
                errors += _scan_owners(
                    document=document,
                    owners=eligible,
                    session_getter=session_getter,
                    workers=args.workers,
                    checkpoint_every=args.checkpoint_every,
                    output=output,
                )
            else:
                print("No owner pages require scanning.")

            referenced_vessels = current_vessel_references(document["owners"])
            vessel_specs = document.setdefault("vessel_specifications", {})
            refresh_vessel_ids = {
                relationship["vessel_id"]
                for owner in eligible
                for relationship in owner.get("vessel_ownership", {}).get(
                    "relationships", []
                )
                if relationship.get("is_current")
            }
            vessels_to_scan = [
                vessel
                for vessel_id, vessel in referenced_vessels.items()
                if (
                    args.refresh and vessel_id in refresh_vessel_ids
                )
                or vessel_specs.get(str(vessel_id), {}).get("status") != "ok"
            ]
            if vessels_to_scan:
                errors += _scan_vessels(
                    document=document,
                    vessels=vessels_to_scan,
                    session_getter=session_getter,
                    workers=args.workers,
                    checkpoint_every=args.checkpoint_every,
                    output=output,
                )
            else:
                print("No vessel specifications require scanning.")
    except Exception as exc:
        print(f"Vessel enrichment stopped: {exc}", file=sys.stderr)
        atomic_write_json(output, document)
        return 1

    vessel_specs = document.setdefault("vessel_specifications", {})
    for owner in document["owners"]:
        apply_owner_vessel_ranking(owner, vessel_specs)
    sort_and_rank_owners(document)

    ranked_count = sum(
        owner.get("vessel_ownership", {}).get("ranking_status") == "ranked"
        for owner in document["owners"]
    )
    incomplete_count = sum(
        owner.get("vessel_ownership", {}).get("ranking_status") == "incomplete"
        for owner in document["owners"]
    )
    current_owner_count = sum(
        bool(owner.get("vessel_ownership", {}).get("current_vessels"))
        for owner in document["owners"]
    )
    owner_scan_ok_count = sum(
        owner.get("vessel_ownership", {}).get("status") == "ok"
        for owner in document["owners"]
    )
    owner_scan_error_count = sum(
        owner.get("vessel_ownership", {}).get("status") == "error"
        for owner in document["owners"]
    )
    owner_scan_pending_count = (
        len(document["owners"]) - owner_scan_ok_count - owner_scan_error_count
    )
    document["vessel_enrichment"] = {
        "status": (
            "complete"
            if not owner_scan_pending_count
            and not owner_scan_error_count
            and not incomplete_count
            else "partial"
        ),
        "updated_at": utc_now(),
        "sort": "largest_known_current_loa_m_desc",
        "owner_count": len(document["owners"]),
        "owner_scan_ok_count": owner_scan_ok_count,
        "owner_scan_error_count": owner_scan_error_count,
        "owner_scan_pending_count": owner_scan_pending_count,
        "current_owner_count": current_owner_count,
        "ranked_owner_count": ranked_count,
        "incomplete_owner_count": incomplete_count,
        "vessel_specification_count": len(vessel_specs),
    }
    atomic_write_json(output, document)

    print(
        f"Vessel enrichment complete: {current_owner_count} current owners, "
        f"{ranked_count} fully ranked, {incomplete_count} incomplete. "
        f"Output: {output}"
    )
    return 1 if errors or incomplete_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
