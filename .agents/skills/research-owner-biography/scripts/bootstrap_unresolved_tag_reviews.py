#!/usr/bin/env python3
"""Create terminal zero-tag checkpoints for fully reviewed unresolved placeholders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DOSSIERS = ROOT / "output" / "owner-research" / "all-by-loa"
DEFAULT_REVIEWS = (
    ROOT / "output" / "owner-research" / "tag-semantic-review" / "reviews"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create explicit zero-tag semantic-review checkpoints only for "
            "unresolved placeholders whose completed dossiers contain no proposed tags."
        )
    )
    parser.add_argument("--dossiers", type=Path, default=DEFAULT_DOSSIERS)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def eligible(dossier: dict) -> bool:
    return (
        dossier.get("record_type") == "unresolved_placeholder"
        and dossier.get("research_status") == "insufficient_evidence"
        and dossier.get("review", {}).get("status") == "complete"
        and not dossier.get("proposed_tags")
        and bool(dossier.get("sources"))
    )


def checkpoint_for(path: Path, dossier: dict) -> dict:
    owner = dossier["owner"]
    return {
        "schema_version": 1,
        "person_id": owner["person_id"],
        "display_name": owner["display_name"],
        "dossier_sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        "status": "reviewed",
        "existing_tags_complete": True,
        "canonical_tags": [],
        "catalogue_candidates": [],
        "rejected_candidates": [
            {
                "name": "Government-owned",
                "reason": (
                    "The unresolved record contains no evidence that its owner is a "
                    "government, public body or state-owned entity."
                ),
            }
        ],
        "zero_tag_reason": (
            "The completed dossier classifies this record as an unresolved placeholder "
            "and establishes no reliable owner identity, organisation, occupation, "
            "business, wealth source or other durable non-vessel attribute. Semantic "
            "tags are therefore withheld until reliable identity evidence is found."
        ),
    }


def main() -> int:
    args = parse_args()
    dossiers = args.dossiers.resolve()
    reviews = args.reviews.resolve()
    planned: list[tuple[Path, dict]] = []

    for path in sorted(dossiers.glob("*.research.json")):
        dossier = load_json(path)
        if not eligible(dossier):
            continue
        person_id = dossier["owner"]["person_id"]
        target = reviews / f"{person_id}.json"
        if target.exists():
            continue
        planned.append((target, checkpoint_for(path, dossier)))

    if args.apply:
        reviews.mkdir(parents=True, exist_ok=True)
        for target, checkpoint in planned:
            target.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    mode = "apply" if args.apply else "dry-run"
    print(json.dumps({"mode": mode, "eligible_missing_reviews": len(planned)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
