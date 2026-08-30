from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from duplicate_audit.core import (
    AUDIT_DATASET,
    CANDIDATE_DATASET,
    build_identity_card,
    connected_candidate_clusters,
    file_sha256,
    resolve_final_classification,
    validate_judgment,
)
from duplicate_audit.report import render_audit_report, summarize_candidates
from src.io_utils import (
    atomic_write_json,
    atomic_write_text,
    load_json,
    load_json_unvalidated,
    utc_now,
)


REVIEW_DATASET = "owner_duplicate_codex_review_batch"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Codex duplicate judgments and compile HTML/JSON reports."
    )
    parser.add_argument("--owners", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    return parser


def _load_reviews(review_dir: Path) -> dict[str, dict[str, Any]]:
    review_files = sorted(review_dir.glob("batch-*.review.json"))
    if not review_files:
        raise ValueError(f"No batch-*.review.json files found in {review_dir}")
    result: dict[str, dict[str, Any]] = {}
    seen_batches: set[str] = set()
    for path in review_files:
        document = load_json_unvalidated(path)
        if document.get("dataset") != REVIEW_DATASET:
            raise ValueError(f"{path} has the wrong dataset type")
        batch_id = document.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            raise ValueError(f"{path} has no batch_id")
        if batch_id in seen_batches:
            raise ValueError(f"Duplicate review batch_id {batch_id}")
        seen_batches.add(batch_id)
        if document.get("reviewer") != "codex":
            raise ValueError(f"{path} reviewer must be 'codex'")
        judgments = document.get("judgments")
        if not isinstance(judgments, list):
            raise ValueError(f"{path} has no judgments array")
        for item in judgments:
            if not isinstance(item, Mapping):
                raise ValueError(f"{path} contains a non-object judgment")
            candidate_id = item.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ValueError(f"{path} contains a judgment without candidate_id")
            if candidate_id in result:
                raise ValueError(f"Duplicate judgment for {candidate_id}")
            result[candidate_id] = dict(item)
    return result


def _validated_candidate(
    candidate: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    owners_by_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    person_ids = [int(value) for value in candidate["person_ids"]]
    reviewed_ids = review.get("person_ids")
    if reviewed_ids != person_ids:
        raise ValueError(
            f"{candidate['candidate_id']} person_ids do not match the candidate input"
        )
    primary_value = review.get("primary")
    if not isinstance(primary_value, Mapping):
        raise ValueError(f"{candidate['candidate_id']} has no primary judgment")
    primary = validate_judgment(primary_value, person_ids=person_ids)

    verifier_value = review.get("verifier")
    verifier: dict[str, Any] | None = None
    if verifier_value is not None:
        if not isinstance(verifier_value, Mapping):
            raise ValueError(
                f"{candidate['candidate_id']} verifier must be an object or null"
            )
        verifier = validate_judgment(verifier_value, person_ids=person_ids)
    if primary["classification"] == "probable_duplicate" and verifier is None:
        raise ValueError(
            f"{candidate['candidate_id']} probable primary requires a skeptical verifier"
        )

    final_classification = resolve_final_classification(primary, verifier)
    records = []
    for person_id in person_ids:
        owner = owners_by_id.get(person_id)
        if owner is None:
            raise ValueError(
                f"{candidate['candidate_id']} references missing owner {person_id}"
            )
        records.append(build_identity_card(owner))
    return {
        **candidate,
        "records": records,
        "primary": {"judgment": primary, "agent": {"reviewer": "codex"}},
        "verifier": (
            {"judgment": verifier, "agent": {"reviewer": "codex_skeptical_pass"}}
            if verifier
            else None
        ),
        "final_classification": final_classification,
        "processing_error": None,
        "manual_review": {"decision": "unreviewed", "notes": ""},
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.output_json.exists() or args.output_html.exists():
        print("Refusing to overwrite an existing compiled report", file=sys.stderr)
        return 1
    try:
        owners = load_json(args.owners)
        owners_by_id = {
            int(owner["person_id"]): owner for owner in owners["owners"]
        }
        candidate_document = load_json_unvalidated(args.candidates)
        if candidate_document.get("dataset") != CANDIDATE_DATASET:
            raise ValueError("Candidate input has the wrong dataset type")
        candidates = candidate_document.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Candidate input contains no candidates array")
        reviews = _load_reviews(args.review_dir)
        expected_ids = {candidate["candidate_id"] for candidate in candidates}
        reviewed_ids = set(reviews)
        missing = sorted(expected_ids - reviewed_ids)
        unexpected = sorted(reviewed_ids - expected_ids)
        if missing or unexpected:
            raise ValueError(
                f"Review coverage mismatch: missing={missing}, unexpected={unexpected}"
            )
        compiled_candidates = [
            _validated_candidate(
                candidate,
                reviews[candidate["candidate_id"]],
                owners_by_id=owners_by_id,
            )
            for candidate in candidates
        ]
        audit = {
            "schema_version": 1,
            "dataset": AUDIT_DATASET,
            "generated_at": utc_now(),
            "source": {
                **candidate_document.get("source", {}),
                "evidence_snapshot": str(args.owners.resolve()),
                "evidence_snapshot_sha256": file_sha256(args.owners),
                "candidate_snapshot": str(args.candidates.resolve()),
                "candidate_snapshot_sha256": file_sha256(args.candidates),
                "review_directory": str(args.review_dir.resolve()),
                "live_writes_performed": False,
            },
            "configuration": {
                **candidate_document.get("configuration", {}),
                "review_mode": "codex_skill",
                "hosted_api_used": False,
                "prompt_excludes": [
                    "biography",
                    "long_biography",
                    "internal_notes",
                ],
            },
            "summary": summarize_candidates(compiled_candidates),
            "clusters": connected_candidate_clusters(compiled_candidates),
            "candidates": compiled_candidates,
        }
        atomic_write_json(args.output_json, audit)
        atomic_write_text(args.output_html, render_audit_report(audit))
    except Exception as exc:
        print(f"Review compilation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Compiled {len(compiled_candidates)} reviewed pair(s): "
        f"JSON={args.output_json}; HTML={args.output_html}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
