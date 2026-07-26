from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.auth import authenticated_context, fetch_html
from src.constants import OWNER_REPORT_URL
from src.io_utils import atomic_write_json, new_document, new_owner, utc_now
from src.parsers import parse_owner_list


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export every owner from the paginated SYN owner report."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/owners-list.json"),
        help="JSON output path (default: output/owners-list.json)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Stop after this many pages; intended for smoke testing.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome without a visible window.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    document = new_document()
    document["source"] = {
        "report_url": OWNER_REPORT_URL,
        "pages_exported": 0,
        "reported_last_page": None,
        "owner_count": 0,
        "warnings": [],
    }
    seen_ids: set[int] = set()
    seen_urls: set[str] = set()
    next_url: str | None = OWNER_REPORT_URL

    try:
        with authenticated_context(headless=args.headless) as context:
            while next_url:
                if next_url in seen_urls:
                    raise RuntimeError(f"Pagination loop detected at {next_url}")
                if (
                    args.max_pages is not None
                    and document["source"]["pages_exported"] >= args.max_pages
                ):
                    break
                seen_urls.add(next_url)
                page_number = document["source"]["pages_exported"] + 1
                print(f"Exporting owner report page {page_number}...")
                html = fetch_html(
                    context.session,
                    next_url,
                    expected_marker="jsYayContactResultsTable",
                )
                rows, discovered_next, reported_last = parse_owner_list(
                    html, page_url=next_url
                )
                for row in rows:
                    person_id = row["person_id"]
                    if person_id in seen_ids:
                        document["source"]["warnings"].append(
                            f"Duplicate person_id {person_id} skipped on page {page_number}"
                        )
                        continue
                    seen_ids.add(person_id)
                    document["owners"].append(
                        new_owner(
                            person_id=person_id,
                            profile_url=row["profile_url"],
                            report=row["report"],
                        )
                    )
                document["source"]["pages_exported"] = page_number
                document["source"]["reported_last_page"] = reported_last
                document["source"]["owner_count"] = len(document["owners"])
                document["exported_at"] = utc_now()
                atomic_write_json(args.output, document)
                next_url = discovered_next
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Exported {len(document['owners'])} owners from "
        f"{document['source']['pages_exported']} pages to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
