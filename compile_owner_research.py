from __future__ import annotations

import argparse
import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

from src.io_utils import atomic_write_json, atomic_write_text, load_json
from src.research_batch import (
    RESEARCH_SELECTIONS,
    attach_biography_comparisons,
    compile_research_batch,
    load_dossiers,
    render_research_report,
    select_research_owners,
)
from src.tags import DEFAULT_TAG_CATALOGUE_PATH, load_tag_catalogue


REPO_ROOT = Path(__file__).resolve().parent
DOSSIER_VALIDATOR = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "research-owner-biography"
    / "scripts"
    / "validate_dossier.py"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile owner research dossiers into a separate owner JSON and "
            "standalone HTML review report."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dossier-dir", required=True, type=Path)
    parser.add_argument(
        "--tag-catalogue",
        type=Path,
        default=DEFAULT_TAG_CATALOGUE_PATH,
        help=(
            "Canonical research-layer tag catalogue used to resolve dossier "
            "tag IDs, names, aliases, and merges."
        ),
    )
    parser.add_argument(
        "--compare-dossier-dir",
        type=Path,
        help=(
            "Optional earlier dossier directory used only to render "
            "before-and-after biography and wealth-classification "
            "comparisons in the HTML report."
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--live-biography-baseline",
        type=Path,
        help=(
            "Freshly enriched owner JSON whose current biography values "
            "replace only the compiled owners' biography baselines. Desired "
            "biographies still come from the validated dossiers."
        ),
    )
    parser.add_argument(
        "--selection",
        choices=sorted(RESEARCH_SELECTIONS),
        default="top-100",
        help=(
            "Owner ordering: current YB Top-100 rank (default), fully ranked "
            "largest current-vessel LOA, or all owners prioritised by LOA."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="First N owners in the selected ordering.",
    )
    parser.add_argument(
        "--mark-ai-enriched",
        action="store_true",
        help=(
            "Require complete or legacy-approved dossiers and set "
            "workflow.ai_enriched=true for usable research."
        ),
    )
    return parser


def _default_output(
    input_path: Path,
    limit: int | None,
    selection: str,
) -> Path:
    selection_marker = (
        "" if selection == "top-100" else f".{selection}"
    )
    marker = f".first-{limit}" if limit is not None else ""
    source_stem = input_path.stem.removesuffix(".enriched")
    return input_path.with_name(
        f"research-enriched-{source_stem}{selection_marker}{marker}.json"
    )


def _validate_dossiers(
    dossiers: dict[int, dict[str, Any]],
    paths: dict[int, Path],
    selected_ids: list[int],
    owner_input: Path,
    owner_document: dict[str, Any],
    tag_catalogue: Any,
) -> None:
    validator = _load_dossier_validator()
    for person_id in selected_ids:
        path = paths.get(person_id)
        if path is None:
            continue
        dossier = dossiers[person_id]
        errors, warnings = validator.validate(
            dossier,
            tag_catalogue=tag_catalogue,
        )
        errors.extend(
            validator.validate_owner_document(
                dossier,
                owner_document,
                owner_input,
            )
        )
        errors.extend(f"strict editorial: {warning}" for warning in warnings)
        if errors:
            detail = "\n".join(f"ERROR: {error}" for error in errors)
            raise ValueError(f"Invalid dossier for person_id {person_id}: {detail}")


def _load_dossier_validator() -> ModuleType:
    module_name = "owner_biography_dossier_validator"
    spec = importlib.util.spec_from_file_location(module_name, DOSSIER_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load dossier validator: {DOSSIER_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    script_directory = str(DOSSIER_VALIDATOR.parent)
    sys.path.insert(0, script_directory)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(script_directory)
    return module


def _attach_live_biography_baselines(
    derived: dict[str, Any],
    live_document: dict[str, Any],
    *,
    baseline_path: Path,
) -> None:
    live_by_id = {
        owner.get("person_id"): owner
        for owner in live_document.get("owners", [])
        if isinstance(owner, dict)
    }
    for owner in derived.get("owners", []):
        person_id = owner.get("person_id")
        live_owner = live_by_id.get(person_id)
        if not isinstance(live_owner, dict):
            raise ValueError(
                f"Live biography baseline has no owner {person_id}"
            )
        if live_owner.get("enrichment", {}).get("status") != "ok":
            raise ValueError(
                f"Live biography baseline owner {person_id} is not enriched"
            )
        live_field = live_owner.get("details", {}).get("biography")
        baseline_field = (
            live_owner.get("_baseline", {})
            .get("details", {})
            .get("biography")
        )
        if not isinstance(live_field, dict) or live_field != baseline_field:
            raise ValueError(
                f"Live biography baseline owner {person_id} is not a clean "
                "current snapshot"
            )
        owner_baseline = owner.get("_baseline")
        if not isinstance(owner_baseline, dict):
            raise ValueError(f"Compiled owner {person_id} has no baseline")
        baseline_details = owner_baseline.get("details")
        if not isinstance(baseline_details, dict):
            raise ValueError(
                f"Compiled owner {person_id} has no details baseline"
            )
        baseline_details["biography"] = deepcopy(live_field)

    derived["live_biography_baseline"] = {
        "source_path": str(baseline_path).replace("\\", "/"),
        "owner_count": len(derived.get("owners", [])),
    }


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit <= 0:
        print("--limit must be greater than zero", file=sys.stderr)
        return 1

    output = args.output or _default_output(
        args.input,
        args.limit,
        args.selection,
    )
    report_path = args.report or output.with_suffix(".html")
    try:
        if output.resolve() == args.input.resolve():
            raise ValueError("Output must not overwrite the input owner document")
        document = load_json(args.input)
        tag_catalogue = load_tag_catalogue(args.tag_catalogue)
        dossiers, paths = load_dossiers(args.dossier_dir)
        selected = select_research_owners(
            document,
            args.selection,
            args.limit,
        )
        selected_ids = [owner["person_id"] for owner in selected]
        _validate_dossiers(
            dossiers,
            paths,
            selected_ids,
            args.input,
            document,
            tag_catalogue,
        )
        derived, report = compile_research_batch(
            document,
            dossiers,
            paths,
            source_path=str(args.input),
            limit=args.limit,
            mark_ai_enriched=args.mark_ai_enriched,
            selection=args.selection,
            tag_catalogue=tag_catalogue,
        )
        if args.live_biography_baseline is not None:
            live_document = load_json(args.live_biography_baseline)
            _attach_live_biography_baselines(
                derived,
                live_document,
                baseline_path=args.live_biography_baseline,
            )
        if args.compare_dossier_dir is not None:
            comparison_dossiers, _ = load_dossiers(
                args.compare_dossier_dir
            )
            attach_biography_comparisons(
                report,
                comparison_dossiers,
                source_directory=str(args.compare_dossier_dir),
            )
        atomic_write_json(output, derived)
        atomic_write_text(report_path, render_research_report(report))
    except Exception as exc:
        print(f"Research compilation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Compiled {len(derived['owners'])} owners using "
        f"selection={args.selection}. JSON: {output}. "
        f"Review report: {report_path}"
    )
    if not args.mark_ai_enriched:
        print(
            "workflow.ai_enriched remains false "
            "and the file is not eligible for --ai-enriched-only updates."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
