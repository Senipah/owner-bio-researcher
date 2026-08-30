from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from duplicate_audit.core import CANDIDATE_DATASET, build_identity_card, file_sha256
from src.io_utils import atomic_write_json, load_json, load_json_unvalidated, utc_now


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare bounded identity-evidence bundles for Codex review."
    )
    parser.add_argument("--owners", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=20)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_size < 1 or args.batch_size > 50:
        print("--batch-size must be between 1 and 50", file=sys.stderr)
        return 1
    existing = list(args.output_dir.glob("batch-*.json")) if args.output_dir.exists() else []
    if existing:
        print(
            f"Refusing to overwrite {len(existing)} existing review batch file(s) "
            f"in {args.output_dir}",
            file=sys.stderr,
        )
        return 1
    try:
        owners = load_json(args.owners)
        candidate_document = load_json_unvalidated(args.candidates)
        if candidate_document.get("dataset") != CANDIDATE_DATASET:
            raise ValueError("Candidate input has the wrong dataset type")
        candidates = candidate_document.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Candidate input contains no candidates array")
        owners_by_id = {
            int(owner["person_id"]): owner for owner in owners["owners"]
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        batch_count = math.ceil(len(candidates) / args.batch_size)
        files: list[dict[str, Any]] = []
        for batch_index in range(batch_count):
            start = batch_index * args.batch_size
            selected = candidates[start : start + args.batch_size]
            batch_id = f"batch-{batch_index + 1:03d}"
            bundled_candidates = []
            for candidate in selected:
                person_ids = [int(value) for value in candidate["person_ids"]]
                missing = [value for value in person_ids if value not in owners_by_id]
                if missing:
                    raise ValueError(
                        f"Candidate {candidate['candidate_id']} references missing "
                        f"owners {missing}"
                    )
                bundled_candidates.append(
                    {
                        **candidate,
                        "records": [
                            build_identity_card(owners_by_id[person_id])
                            for person_id in person_ids
                        ],
                    }
                )
            batch_path = args.output_dir / f"{batch_id}.json"
            atomic_write_json(
                batch_path,
                {
                    "schema_version": 1,
                    "dataset": "owner_duplicate_codex_review_input_batch",
                    "batch_id": batch_id,
                    "generated_at": utc_now(),
                    "source": {
                        "owners": str(args.owners.resolve()),
                        "owners_sha256": file_sha256(args.owners),
                        "candidates": str(args.candidates.resolve()),
                        "candidates_sha256": file_sha256(args.candidates),
                    },
                    "candidate_count": len(bundled_candidates),
                    "candidates": bundled_candidates,
                },
            )
            files.append(
                {
                    "batch_id": batch_id,
                    "path": str(batch_path.resolve()),
                    "candidate_count": len(bundled_candidates),
                }
            )
        atomic_write_json(
            args.output_dir / "manifest.json",
            {
                "schema_version": 1,
                "dataset": "owner_duplicate_codex_review_manifest",
                "generated_at": utc_now(),
                "candidate_count": len(candidates),
                "batch_size": args.batch_size,
                "batch_count": batch_count,
                "batches": files,
            },
        )
    except Exception as exc:
        print(f"Review batch preparation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Prepared {len(candidates)} candidate pair(s) in {batch_count} "
        f"batch(es) beneath {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
