from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from duplicate_audit.adjudication import adjudicate_candidate
from duplicate_audit.core import (
    AUDIT_DATASET,
    CANDIDATE_DATASET,
    build_identity_card,
    connected_candidate_clusters,
    discover_candidates,
    embedding_views,
    file_sha256,
)
from duplicate_audit.live import (
    enrich_owner_ids_live,
    export_live_owner_snapshot,
)
from duplicate_audit.openai_api import OpenAIAPIClient
from duplicate_audit.report import render_audit_report, summarize_candidates
from src.io_utils import (
    atomic_write_json,
    atomic_write_text,
    load_json,
    load_json_unvalidated,
    utc_now,
)


def _default_output_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Path("output") / "duplicate-audit" / stamp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a read-only, AI-assisted report of possible duplicate "
            "owner records. This command has no live write capability."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--live",
        action="store_true",
        help="Export the complete live owner report before auditing.",
    )
    source.add_argument(
        "--input",
        type=Path,
        help="Audit a supplied owner JSON instead of creating a live list export.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="New audit directory (default: output/duplicate-audit/TIMESTAMP).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a checkpointed run in an explicitly supplied output directory.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use a headless browser for SYN authentication.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Live-export page limit for smoke tests only.",
    )
    parser.add_argument(
        "--exhaustive-live-enrichment",
        action="store_true",
        help=(
            "Read details and socials for every owner before candidate discovery. "
            "This is much heavier than the default candidate-first flow."
        ),
    )
    parser.add_argument(
        "--enrich-candidates-live",
        action="store_true",
        help=(
            "When --input is used, re-read live details/socials for candidate IDs. "
            "Candidate enrichment is already the default for --live."
        ),
    )

    parser.add_argument(
        "--allow-ai-upload",
        action="store_true",
        help=(
            "Acknowledge that allow-listed identity fields will be sent to the "
            "OpenAI API for embeddings and judgments."
        ),
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the OpenAI API key.",
    )
    parser.add_argument(
        "--api-base",
        default="https://api.openai.com/v1",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-large",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=1024,
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=128,
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-5.4-mini",
    )
    parser.add_argument(
        "--verifier-model",
        default="gpt-5.4",
    )
    parser.add_argument(
        "--no-verifier",
        action="store_true",
        help="Do not run the second skeptical pass for probable matches.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
    )

    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--name-similarity-threshold",
        type=float,
        default=0.82,
    )
    parser.add_argument(
        "--identity-similarity-threshold",
        type=float,
        default=0.76,
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=2000,
        help=(
            "Safety ceiling for paid pair judgments. The command stops instead "
            "of silently truncating when this is exceeded."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Judge only the first N retrieved pairs; intended for smoke tests.",
    )
    return parser


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.allow_ai_upload:
        parser.error(
            "--allow-ai-upload is required because owner identity fields are sent "
            "to a hosted model"
        )
    if args.resume and args.output_dir is None:
        parser.error("--resume requires an explicit --output-dir")
    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages must be at least 1")
    if args.exhaustive_live_enrichment and not args.live:
        parser.error("--exhaustive-live-enrichment requires --live")
    if args.enrich_candidates_live and args.live:
        parser.error(
            "--enrich-candidates-live is unnecessary with --live; it is already "
            "the default"
        )
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    if args.embedding_dimensions < 1:
        parser.error("--embedding-dimensions must be at least 1")
    if args.embedding_batch_size < 1:
        parser.error("--embedding-batch-size must be at least 1")
    for name in ("name_similarity_threshold", "identity_similarity_threshold"):
        value = getattr(args, name)
        if not -1.0 <= value <= 1.0:
            parser.error(f"--{name.replace('_', '-')} must be between -1 and 1")
    if args.max_candidates < 1:
        parser.error("--max-candidates must be at least 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")


def _prepare_output_dir(path: Path, *, resume: bool) -> None:
    if path.exists() and any(path.iterdir()) and not resume:
        raise ValueError(
            f"Output directory is not empty: {path}. Choose a new directory or "
            "use --resume."
        )
    path.mkdir(parents=True, exist_ok=True)


def _load_or_create_source(
    args: argparse.Namespace,
    output_dir: Path,
) -> tuple[dict[str, Any], Path]:
    snapshot_path = output_dir / "live-owners.json"
    if args.live:
        if args.resume and snapshot_path.exists():
            document = load_json(snapshot_path)
            complete = bool(document.get("source", {}).get("complete"))
            limited = args.max_pages is not None
            if complete or limited:
                print(f"Reusing checkpointed live snapshot: {snapshot_path}")
                return document, snapshot_path
        document = export_live_owner_snapshot(
            output_path=snapshot_path,
            headless=args.headless,
            max_pages=args.max_pages,
        )
        return document, snapshot_path

    snapshot_path = output_dir / "source-owners.json"
    if args.resume and snapshot_path.exists():
        return load_json(snapshot_path), snapshot_path
    document = load_json(args.input)
    atomic_write_json(snapshot_path, document)
    return document, snapshot_path


def _load_or_create_embeddings(
    client: OpenAIAPIClient,
    *,
    cards: list[dict[str, Any]],
    output_dir: Path,
    source_hash: str,
    model: str,
    dimensions: int,
    batch_size: int,
    resume: bool,
) -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "numpy is required. Run: .\\venv\\Scripts\\python.exe -m pip "
            "install -r duplicate_audit\\requirements.txt"
        ) from exc

    cache_path = output_dir / "embeddings.npz"
    metadata_path = output_dir / "embeddings.metadata.json"
    person_ids = [int(card["person_id"]) for card in cards]
    if resume and cache_path.exists() and metadata_path.exists():
        metadata = load_json_unvalidated(metadata_path)
        if (
            metadata.get("source_sha256") != source_hash
            or metadata.get("model") != model
            or metadata.get("dimensions") != dimensions
            or metadata.get("person_ids") != person_ids
        ):
            raise ValueError(
                "The embedding checkpoint does not match this source or configuration"
            )
        print(f"Reusing checkpointed embeddings: {cache_path}")
        with np.load(cache_path) as cache:
            return {"name": cache["name"], "identity": cache["identity"]}

    views = [embedding_views(card) for card in cards]
    result: dict[str, Any] = {}
    for view_name in ("name", "identity"):
        print(f"Creating {view_name} embeddings for {len(cards)} owners...")
        vectors = client.create_embeddings(
            [view[view_name] for view in views],
            model=model,
            dimensions=dimensions,
            batch_size=batch_size,
        )
        result[view_name] = np.asarray(vectors, dtype=np.float32)

    np.savez_compressed(cache_path, name=result["name"], identity=result["identity"])
    atomic_write_json(
        metadata_path,
        {
            "dataset": "owner_duplicate_embedding_cache",
            "created_at": utc_now(),
            "source_sha256": source_hash,
            "model": model,
            "dimensions": dimensions,
            "person_ids": person_ids,
        },
    )
    return result


def _load_or_create_candidates(
    client: OpenAIAPIClient,
    *,
    document: dict[str, Any],
    output_dir: Path,
    source_path: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    candidate_path = output_dir / "candidates.json"
    thresholds = {
        "name": args.name_similarity_threshold,
        "identity": args.identity_similarity_threshold,
    }
    expected_configuration = {
        "embedding_model": args.embedding_model,
        "embedding_dimensions": args.embedding_dimensions,
        "top_k": args.top_k,
        "similarity_thresholds": thresholds,
    }
    if args.resume and candidate_path.exists():
        candidate_document = load_json_unvalidated(candidate_path)
        if candidate_document.get("dataset") != CANDIDATE_DATASET:
            raise ValueError("Candidate checkpoint has the wrong dataset type")
        if candidate_document.get("source", {}).get("owner_snapshot_sha256") != file_sha256(
            source_path
        ):
            raise ValueError("Candidate checkpoint does not match the owner snapshot")
        if candidate_document.get("configuration") != expected_configuration:
            raise ValueError(
                "Candidate checkpoint does not match the requested embedding or "
                "retrieval configuration"
            )
        print(f"Reusing checkpointed candidates: {candidate_path}")
        return candidate_document

    cards = [build_identity_card(owner) for owner in document["owners"]]
    source_hash = file_sha256(source_path)
    embeddings = _load_or_create_embeddings(
        client,
        cards=cards,
        output_dir=output_dir,
        source_hash=source_hash,
        model=args.embedding_model,
        dimensions=args.embedding_dimensions,
        batch_size=args.embedding_batch_size,
        resume=args.resume,
    )
    candidates = discover_candidates(
        cards,
        embeddings,
        thresholds=thresholds,
        top_k=args.top_k,
    )
    candidate_document = {
        "schema_version": 1,
        "dataset": CANDIDATE_DATASET,
        "generated_at": utc_now(),
        "source": {
            "owner_snapshot": str(source_path.resolve()),
            "owner_snapshot_sha256": source_hash,
            "owner_exported_at": document.get("exported_at"),
            "owner_count": len(document["owners"]),
        },
        "configuration": expected_configuration,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    atomic_write_json(candidate_path, candidate_document)
    return candidate_document


def _candidate_owner_ids(candidates: list[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            int(person_id)
            for candidate in candidates
            for person_id in candidate["person_ids"]
        }
    )


def _load_or_enrich_evidence(
    args: argparse.Namespace,
    *,
    source_document: dict[str, Any],
    person_ids: list[int],
    output_dir: Path,
) -> tuple[dict[str, Any], Path | None]:
    should_enrich = args.live or args.enrich_candidates_live
    if not should_enrich:
        return source_document, None
    evidence_path = output_dir / "candidate-evidence.live.json"
    if args.resume and evidence_path.exists():
        base = load_json(evidence_path)
    else:
        base = source_document
    evidence = enrich_owner_ids_live(
        base,
        person_ids=person_ids,
        output_path=evidence_path,
        headless=args.headless,
    )
    return evidence, evidence_path


def _load_or_enrich_all(
    args: argparse.Namespace,
    *,
    source_document: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], Path]:
    path = output_dir / "live-owners.exhaustively-enriched.json"
    if args.resume and path.exists():
        base = load_json(path)
    else:
        base = source_document
    document = enrich_owner_ids_live(
        base,
        person_ids=[int(owner["person_id"]) for owner in base["owners"]],
        output_path=path,
        headless=args.headless,
    )
    return document, path


def _new_audit_document(
    *,
    candidate_document: dict[str, Any],
    source_document: dict[str, Any],
    source_path: Path,
    evidence_path: Path | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "dataset": AUDIT_DATASET,
        "generated_at": utc_now(),
        "source": {
            **candidate_document["source"],
            "owner_snapshot": str(source_path.resolve()),
            "owner_snapshot_sha256": file_sha256(source_path),
            "owner_count": len(source_document["owners"]),
            "evidence_snapshot": str(evidence_path.resolve()) if evidence_path else None,
            "evidence_snapshot_sha256": (
                file_sha256(evidence_path) if evidence_path else None
            ),
            "live_writes_performed": False,
        },
        "configuration": {
            **candidate_document["configuration"],
            "judge_model": args.judge_model,
            "verifier_model": None if args.no_verifier else args.verifier_model,
            "reasoning_effort": args.reasoning_effort,
            "api_store": False,
            "prompt_excludes": ["biography", "long_biography", "internal_notes"],
            "candidate_limit": args.limit,
        },
        "summary": {},
        "clusters": [],
        "candidates": [],
    }


def _run_judgments(
    client: OpenAIAPIClient,
    *,
    audit: dict[str, Any],
    candidates: list[dict[str, Any]],
    evidence_document: dict[str, Any],
    audit_path: Path,
    args: argparse.Namespace,
) -> int:
    owners_by_id = {
        int(owner["person_id"]): owner for owner in evidence_document["owners"]
    }
    existing = {
        candidate["candidate_id"]: candidate
        for candidate in audit.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    errors = 0
    total = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        candidate_id = candidate["candidate_id"]
        previous = existing.get(candidate_id)
        if previous and previous.get("final_classification") and not previous.get(
            "processing_error"
        ):
            print(f"[{index}/{total}] Reusing judgment {candidate_id}")
            continue

        left_id, right_id = (int(value) for value in candidate["person_ids"])
        left_card = build_identity_card(owners_by_id[left_id])
        right_card = build_identity_card(owners_by_id[right_id])
        result: dict[str, Any] = {
            **candidate,
            "records": [left_card, right_card],
            "manual_review": {"decision": "unreviewed", "notes": ""},
        }
        print(f"[{index}/{total}] AI review {candidate_id}")
        try:
            adjudication = adjudicate_candidate(
                client,
                left=left_card,
                right=right_card,
                retrieval=candidate["retrieval"],
                judge_model=args.judge_model,
                verifier_model=None if args.no_verifier else args.verifier_model,
                reasoning_effort=args.reasoning_effort,
            )
            result.update(adjudication)
            result["processing_error"] = None
        except Exception as exc:
            errors += 1
            result["primary"] = None
            result["verifier"] = None
            result["final_classification"] = "unprocessed"
            result["processing_error"] = str(exc)
            print(f"  Judgment failed: {exc}", file=sys.stderr)
        existing[candidate_id] = result
        audit["candidates"] = [
            existing[item["candidate_id"]]
            for item in candidates
            if item["candidate_id"] in existing
        ]
        audit["generated_at"] = utc_now()
        audit["summary"] = summarize_candidates(audit["candidates"])
        audit["clusters"] = connected_candidate_clusters(audit["candidates"])
        atomic_write_json(audit_path, audit)
    return errors


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(args, parser)
    output_dir = (args.output_dir or _default_output_dir()).resolve()
    try:
        _prepare_output_dir(output_dir, resume=args.resume)
        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise RuntimeError(
                f"The {args.api_key_env} environment variable is not set. "
                "No owner data has been sent to the OpenAI API."
            )
        client = OpenAIAPIClient(api_key, api_base=args.api_base)

        source_document, source_path = _load_or_create_source(args, output_dir)
        discovery_document = source_document
        discovery_path = source_path
        if args.exhaustive_live_enrichment:
            discovery_document, discovery_path = _load_or_enrich_all(
                args,
                source_document=source_document,
                output_dir=output_dir,
            )

        candidate_document = _load_or_create_candidates(
            client,
            document=discovery_document,
            output_dir=output_dir,
            source_path=discovery_path,
            args=args,
        )
        all_candidates = list(candidate_document["candidates"])
        selected_candidates = (
            all_candidates[: args.limit] if args.limit is not None else all_candidates
        )
        if len(selected_candidates) > args.max_candidates:
            raise RuntimeError(
                f"Planned {len(selected_candidates)} paid pair judgments, exceeding "
                f"--max-candidates {args.max_candidates}. Candidates were saved for "
                "inspection; raise the similarity thresholds, use --limit, or "
                "explicitly increase the safety ceiling."
            )
        evidence_document, evidence_path = _load_or_enrich_evidence(
            args,
            source_document=discovery_document,
            person_ids=_candidate_owner_ids(selected_candidates),
            output_dir=output_dir,
        )

        audit_path = output_dir / "duplicate-audit.json"
        if args.resume and audit_path.exists():
            audit = load_json_unvalidated(audit_path)
            if audit.get("dataset") != AUDIT_DATASET:
                raise ValueError("Audit checkpoint has the wrong dataset type")
            if audit.get("source", {}).get("owner_snapshot_sha256") != file_sha256(
                source_path
            ):
                raise ValueError("Audit checkpoint does not match the owner snapshot")
            expected_audit_configuration = {
                "judge_model": args.judge_model,
                "verifier_model": None if args.no_verifier else args.verifier_model,
                "reasoning_effort": args.reasoning_effort,
                "candidate_limit": args.limit,
            }
            actual_audit_configuration = audit.get("configuration", {})
            if any(
                actual_audit_configuration.get(key) != value
                for key, value in expected_audit_configuration.items()
            ):
                raise ValueError(
                    "Audit checkpoint does not match the requested judgment "
                    "configuration"
                )
            audit["source"]["evidence_snapshot"] = (
                str(evidence_path.resolve()) if evidence_path else None
            )
            audit["source"]["evidence_snapshot_sha256"] = (
                file_sha256(evidence_path) if evidence_path else None
            )
        else:
            audit = _new_audit_document(
                candidate_document=candidate_document,
                source_document=source_document,
                source_path=source_path,
                evidence_path=evidence_path,
                args=args,
            )
            atomic_write_json(audit_path, audit)

        errors = _run_judgments(
            client,
            audit=audit,
            candidates=selected_candidates,
            evidence_document=evidence_document,
            audit_path=audit_path,
            args=args,
        )
        audit["generated_at"] = utc_now()
        audit["summary"] = summarize_candidates(audit["candidates"])
        audit["clusters"] = connected_candidate_clusters(audit["candidates"])
        atomic_write_json(audit_path, audit)
        report_path = output_dir / "duplicate-review.html"
        atomic_write_text(report_path, render_audit_report(audit))

        print(
            f"Duplicate audit complete: {len(audit['candidates'])} reviewed pair(s), "
            f"{errors} processing error(s)."
        )
        print(f"JSON: {audit_path}")
        print(f"Report: {report_path}")
        return 1 if errors else 0
    except Exception as exc:
        print(f"Duplicate audit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
