from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.io_utils import atomic_write_json


def _load_resolver() -> Any:
    path = SCRIPT_DIR / "resolve_semantic_tag_candidates.py"
    specification = importlib.util.spec_from_file_location(
        "semantic_tag_candidate_resolver", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


RESOLVER = _load_resolver()


def prepare_draft(
    reviews: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    groups = RESOLVER._candidate_groups(reviews)
    decisions: list[dict[str, Any]] = []
    for key in sorted(groups):
        group = groups[key]
        occurrences = []
        for proposal in group["proposals"]:
            review = proposal["review"]
            occurrences.append(
                {
                    "person_id": review.get("person_id"),
                    "display_name": review.get("display_name"),
                    "summary": proposal["candidate"].get("summary"),
                    "confidence": proposal["candidate"].get("confidence"),
                }
            )
        decisions.append(
            {
                "candidate": group["candidate_names"][0],
                "action": "add",
                "canonical": group["candidate_names"][0],
                "aliases": group["aliases"],
                "facets": group["facets"],
                "occurrences": occurrences,
            }
        )
    return {
        "schema_version": 1,
        "approval_status": "draft",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_file_count": len(reviews),
        "candidate_group_count": len(groups),
        "decisions": decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Draft an explicit, non-applicable decision document for central "
            "semantic review of open-taxonomy tag candidates."
        )
    )
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--reviews", type=Path, default=RESOLVER.DEFAULT_REVIEW_DIR
    )
    parser.add_argument("--review-id", action="append", type=int, default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        parser.error(f"output already exists: {args.output}; use --force")
    reviews = [
        (path, RESOLVER._load_object(path))
        for path in sorted(args.reviews.glob("*.json"))
    ]
    if args.review_id:
        requested = set(args.review_id)
        reviews = [
            (path, review)
            for path, review in reviews
            if review.get("person_id") in requested
        ]
        found = {review.get("person_id") for _, review in reviews}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"review checkpoints not found: {missing}")
    draft = prepare_draft(reviews)
    atomic_write_json(args.output, draft)
    print(
        f"Drafted {draft['candidate_group_count']} candidate decisions from "
        f"{draft['review_file_count']} reviews in {args.output}"
    )
    print("Review every decision and set approval_status to approved before use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
