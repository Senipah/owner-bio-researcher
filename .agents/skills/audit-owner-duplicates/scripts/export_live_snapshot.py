from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from duplicate_audit.live import export_live_owner_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a read-only live owner snapshot for duplicate review."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-pages", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists():
        print(f"Refusing to overwrite existing snapshot: {args.output}", file=sys.stderr)
        return 1
    if args.max_pages is not None and args.max_pages < 1:
        print("--max-pages must be at least 1", file=sys.stderr)
        return 1
    try:
        document = export_live_owner_snapshot(
            output_path=args.output,
            headless=args.headless,
            max_pages=args.max_pages,
        )
    except Exception as exc:
        print(f"Live owner export failed: {exc}", file=sys.stderr)
        return 1
    complete = bool(document.get("source", {}).get("complete"))
    print(
        f"Exported {len(document['owners'])} owners from "
        f"{document['source']['pages_exported']} page(s) to {args.output}; "
        f"complete={complete}"
    )
    return 0 if complete or args.max_pages is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
