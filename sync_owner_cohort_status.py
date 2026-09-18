from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.cohort_status import (
    load_researched_owner_ids,
    load_updated_owner_ids,
    prepare_cohort_status_sync,
)
from src.io_utils import atomic_write_json, load_json_unvalidated


DEFAULT_COHORT = Path("output/owner-research/all-by-loa/cohort.json")
DEFAULT_DOSSIER_DIRECTORY = Path("output/owner-research/all-by-loa")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or synchronize tracked research and verified-update flags "
            "in the canonical all-by-loa cohort."
        )
    )
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument(
        "--dossier-dir", type=Path, default=DEFAULT_DOSSIER_DIRECTORY
    )
    parser.add_argument(
        "--updated-owner-input",
        action="append",
        type=Path,
        default=[],
        help=(
            "Owner JSON whose verified workflow.updated_in_system=true values "
            "should be imported during a migration or verified-update "
            "checkpoint; may be supplied more than once."
        ),
    )
    parser.add_argument("--mark-updated", action="append", type=int, default=[])
    parser.add_argument(
        "--mark-not-updated", action="append", type=int, default=[]
    )
    parser.add_argument(
        "--audit",
        type=Path,
        help="Optional JSON report; ordinary progress synchronization omits it.",
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        cohort = load_json_unvalidated(args.cohort)
        researched = load_researched_owner_ids(args.dossier_dir)
        imported_updated = load_updated_owner_ids(args.updated_owner_input)
        updated, report = prepare_cohort_status_sync(
            cohort,
            researched_owner_ids=researched,
            imported_updated_owner_ids=imported_updated,
            mark_updated_owner_ids=set(args.mark_updated),
            mark_not_updated_owner_ids=set(args.mark_not_updated),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not synchronize cohort status: {exc}", file=sys.stderr)
        return 1

    report.update(
        {
            "mode": "apply" if args.apply else "dry-run",
            "cohort": str(args.cohort.resolve()),
            "dossier_directory": str(args.dossier_dir.resolve()),
            "updated_owner_inputs": [
                str(path.resolve()) for path in args.updated_owner_input
            ],
        }
    )
    if args.apply:
        atomic_write_json(args.cohort, updated)
    if args.audit is not None:
        atomic_write_json(args.audit, report)
    summary = {
        key: value
        for key, value in report.items()
        if key != "changed_person_ids"
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.apply:
        print("Dry-run only; no cohort state was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
