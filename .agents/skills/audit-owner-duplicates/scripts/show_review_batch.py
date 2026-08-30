#!/usr/bin/env python3
"""Print a compact, lossless-enough view of one duplicate review batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.batch.read_text(encoding="utf-8"))
    print(f"{payload['batch_id']} candidates={payload['candidate_count']}")
    for candidate in payload["candidates"]:
        retrieval = candidate["retrieval"]
        print(
            f"\n{candidate['candidate_id']} methods={','.join(retrieval['methods'])} "
            f"name_similarity={retrieval['maximum_name_similarity']} "
            f"signals={_compact(retrieval['signals'])}"
        )
        for record in candidate["records"]:
            details = {key: value for key, value in record["details"].items() if value not in (None, "", [], {})}
            print(
                f"  id={record['person_id']} full_name={record['full_name']!r} "
                f"image={record.get('image_url', '')!r}"
            )
            print(f"    aliases={_compact(record.get('aliases', []))}")
            print(f"    details={_compact(details)}")
            print(f"    known_for={record.get('known_for', '')!r}")
            print(f"    employers={_compact(record.get('employers', []))}")
            print(f"    socials={_compact(record.get('social_profiles', []))}")
            print(f"    vessels={_compact(record.get('vessels', []))}")
            print(f"    enrichment_status={record.get('enrichment_status', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
