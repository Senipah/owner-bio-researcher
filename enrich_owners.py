from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

from src.auth import authenticated_context
from src.enrichment import enrich_owner
from src.io_utils import (
    atomic_write_json,
    derived_output_path,
    load_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enrich an owner export with all details and social profiles."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path (default: INPUT.enriched.json)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing output file and skip successful owners.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-enrich records already marked successful.",
    )
    parser.add_argument(
        "--person-id",
        action="append",
        type=int,
        dest="person_ids",
        help="Only enrich this person ID; may be supplied more than once.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of selected records to process.",
    )
    parser.add_argument("--headless", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = args.output or derived_output_path(args.input, ".enriched")
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
            or owner.get("enrichment", {}).get("status") != "ok"
        )
    ]
    if args.limit is not None:
        eligible = eligible[: args.limit]
    if not eligible:
        print("No owners require enrichment.")
        atomic_write_json(output, document)
        return 0

    errors = 0
    try:
        with authenticated_context(headless=args.headless) as context:
            total = len(eligible)
            for index, owner in enumerate(eligible, start=1):
                person_id = owner["person_id"]
                name = " ".join(
                    filter(
                        None,
                        [
                            owner.get("report", {}).get("first_name"),
                            owner.get("report", {}).get("last_name"),
                        ],
                    )
                )
                print(f"[{index}/{total}] Enriching {person_id} {name}".rstrip())
                try:
                    type_lookup = enrich_owner(context.session, owner)
                    document.setdefault("lookups", {}).setdefault(
                        "social_media_types", {}
                    ).update(type_lookup)
                except Exception as exc:
                    errors += 1
                    owner["enrichment"] = {
                        "status": "error",
                        "enriched_at": None,
                        "error": str(exc),
                    }
                    print(f"  Failed: {exc}", file=sys.stderr)
                atomic_write_json(output, document)
    except Exception as exc:
        print(f"Enrichment stopped: {exc}", file=sys.stderr)
        return 1

    print(
        f"Enrichment complete: {len(eligible) - errors} successful, "
        f"{errors} failed. Output: {output}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
