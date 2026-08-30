from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from duplicate_audit.core import CANDIDATE_DATASET
from duplicate_audit.live import enrich_owner_ids_live
from src.io_utils import load_json, load_json_unvalidated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read live details/socials for duplicate-candidate owner IDs."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.output.exists() and not args.resume:
            raise ValueError(
                f"Output exists; use --resume to continue it: {args.output}"
            )
        source = load_json(args.output if args.resume and args.output.exists() else args.input)
        candidate_document = load_json_unvalidated(args.candidates)
        if candidate_document.get("dataset") != CANDIDATE_DATASET:
            raise ValueError("Candidate input has the wrong dataset type")
        candidates = candidate_document.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Candidate input contains no candidates array")
        person_ids = sorted(
            {
                int(person_id)
                for candidate in candidates
                for person_id in candidate.get("person_ids", [])
            }
        )
        document = enrich_owner_ids_live(
            source,
            person_ids=person_ids,
            output_path=args.output,
            headless=args.headless,
        )
    except Exception as exc:
        print(f"Candidate evidence enrichment failed: {exc}", file=sys.stderr)
        return 1
    requested = set(person_ids)
    errors = [
        owner
        for owner in document["owners"]
        if int(owner["person_id"]) in requested
        and owner.get("enrichment", {}).get("status") != "ok"
    ]
    print(
        f"Candidate evidence written to {args.output}: "
        f"{len(person_ids) - len(errors)} successful, {len(errors)} error(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
