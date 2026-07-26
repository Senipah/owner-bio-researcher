from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    validate_document(document)
    return document


def atomic_write_json(path: str | Path, document: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def validate_document(document: dict[str, Any]) -> None:
    if not isinstance(document, dict):
        raise ValueError("Owner data must be a JSON object")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema_version {document.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION}"
        )
    owners = document.get("owners")
    if not isinstance(owners, list):
        raise ValueError("Owner data must contain an owners array")
    seen: set[int] = set()
    for index, owner in enumerate(owners):
        if not isinstance(owner, dict):
            raise ValueError(f"owners[{index}] must be an object")
        person_id = owner.get("person_id")
        if not isinstance(person_id, int) or person_id <= 0:
            raise ValueError(f"owners[{index}].person_id must be a positive integer")
        if person_id in seen:
            raise ValueError(f"Duplicate person_id in owner data: {person_id}")
        seen.add(person_id)


def new_document() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": utc_now(),
        "source": {},
        "lookups": {"social_media_types": {}},
        "owners": [],
    }


def new_owner(
    *,
    person_id: int,
    profile_url: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "person_id": person_id,
        "profile_url": profile_url,
        "report": report,
        "details": {},
        "social_media_profiles": [],
        "_baseline": None,
        "enrichment": {
            "status": "pending",
            "enriched_at": None,
            "error": None,
        },
    }


def set_baseline(owner: dict[str, Any]) -> None:
    owner["_baseline"] = {
        "details": deepcopy(owner.get("details", {})),
        "social_media_profiles": deepcopy(owner.get("social_media_profiles", [])),
    }


def derived_output_path(input_path: str | Path, suffix: str) -> Path:
    source = Path(input_path)
    return source.with_name(f"{source.stem}{suffix}{source.suffix or '.json'}")
