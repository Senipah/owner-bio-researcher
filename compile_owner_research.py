from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.io_utils import atomic_write_json, atomic_write_text, load_json
from src.research_batch import (
    RESEARCH_SELECTIONS,
    compile_research_batch,
    load_dossiers,
    render_research_report,
    select_research_owners,
)


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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
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
        help="Require approved dossiers and set workflow.ai_enriched=true.",
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
    paths: dict[int, Path],
    selected_ids: list[int],
    owner_input: Path,
) -> None:
    for person_id in selected_ids:
        path = paths.get(person_id)
        if path is None:
            continue
        result = subprocess.run(
            [
                sys.executable,
                str(DOSSIER_VALIDATOR),
                str(path),
                "--owner-input",
                str(owner_input),
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise ValueError(f"Invalid dossier for person_id {person_id}: {detail}")


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
        dossiers, paths = load_dossiers(args.dossier_dir)
        selected = select_research_owners(
            document,
            args.selection,
            args.limit,
        )
        selected_ids = [owner["person_id"] for owner in selected]
        _validate_dossiers(paths, selected_ids, args.input)
        derived, report = compile_research_batch(
            document,
            dossiers,
            paths,
            source_path=str(args.input),
            limit=args.limit,
            mark_ai_enriched=args.mark_ai_enriched,
            selection=args.selection,
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
            "Review state is pending; workflow.ai_enriched remains false "
            "and the file is not eligible for --ai-enriched-only updates."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
