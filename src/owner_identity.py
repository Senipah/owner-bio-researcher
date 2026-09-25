from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import load_json_unvalidated


DEFAULT_OWNER_IDENTITY_RESOLUTIONS_PATH = Path(
    "config/owner-identity-resolutions.json"
)
OWNER_IDENTITY_RESOLUTION_SCHEMA_VERSION = 1
MERGED_DUPLICATE_STATUS = "merged_duplicate"


@dataclass(frozen=True)
class OwnerIdentityResolution:
    retired_person_id: int
    canonical_person_id: int
    archive_path: str
    recorded_on: str
    note: str


def _positive_person_id(value: Any, *, context: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{context} must be a positive integer")
    return value


def load_owner_identity_resolutions(
    path: str | Path = DEFAULT_OWNER_IDENTITY_RESOLUTIONS_PATH,
) -> dict[int, OwnerIdentityResolution]:
    source = Path(path)
    document = load_json_unvalidated(source)
    if not isinstance(document, dict):
        raise ValueError("owner identity resolution root must be an object")
    if document.get("schema_version") != OWNER_IDENTITY_RESOLUTION_SCHEMA_VERSION:
        raise ValueError(
            "owner identity resolution schema_version must be "
            f"{OWNER_IDENTITY_RESOLUTION_SCHEMA_VERSION}"
        )
    raw_resolutions = document.get("resolutions")
    if not isinstance(raw_resolutions, list):
        raise ValueError("owner identity resolutions must be an array")

    resolutions: dict[int, OwnerIdentityResolution] = {}
    for index, raw in enumerate(raw_resolutions):
        context = f"owner identity resolutions[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{context} must be an object")
        if raw.get("status") != MERGED_DUPLICATE_STATUS:
            raise ValueError(
                f"{context}.status must be {MERGED_DUPLICATE_STATUS!r}"
            )
        retired_id = _positive_person_id(
            raw.get("retired_person_id"),
            context=f"{context}.retired_person_id",
        )
        canonical_id = _positive_person_id(
            raw.get("canonical_person_id"),
            context=f"{context}.canonical_person_id",
        )
        if retired_id == canonical_id:
            raise ValueError(
                f"{context} cannot redirect an owner ID to itself"
            )
        if retired_id in resolutions:
            raise ValueError(
                f"duplicate retired_person_id in owner identity resolutions: "
                f"{retired_id}"
            )
        text_values: dict[str, str] = {}
        for key in ("archive_path", "recorded_on", "note"):
            value = raw.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{context}.{key} must be non-empty")
            text_values[key] = value.strip()
        resolutions[retired_id] = OwnerIdentityResolution(
            retired_person_id=retired_id,
            canonical_person_id=canonical_id,
            archive_path=text_values["archive_path"],
            recorded_on=text_values["recorded_on"],
            note=text_values["note"],
        )

    retired_ids = set(resolutions)
    chained_targets = {
        resolution.canonical_person_id
        for resolution in resolutions.values()
        if resolution.canonical_person_id in retired_ids
    }
    if chained_targets:
        raise ValueError(
            "owner identity resolutions must point directly to active canonical "
            "IDs, not another retired ID: "
            + ", ".join(map(str, sorted(chained_targets)))
        )
    return resolutions


def owner_identity_redirects(
    resolutions: dict[int, OwnerIdentityResolution],
) -> dict[int, int]:
    return {
        retired_id: resolution.canonical_person_id
        for retired_id, resolution in resolutions.items()
    }


def validate_owner_identity_archives(
    resolutions: dict[int, OwnerIdentityResolution],
    *,
    repository_root: str | Path = ".",
) -> dict[int, Path]:
    root = Path(repository_root)
    archive_paths: dict[int, Path] = {}
    for retired_id, resolution in resolutions.items():
        archive_path = Path(resolution.archive_path)
        if not archive_path.is_absolute():
            archive_path = root / archive_path
        try:
            document = load_json_unvalidated(archive_path)
        except OSError as exc:
            raise ValueError(
                f"retired owner {retired_id} archive is unavailable: "
                f"{archive_path}"
            ) from exc
        if not isinstance(document, dict):
            raise ValueError(
                f"retired owner {retired_id} archive root must be an object"
            )
        owner = document.get("owner")
        archived_person_id = (
            owner.get("person_id") if isinstance(owner, dict) else None
        )
        if archived_person_id != retired_id:
            raise ValueError(
                f"retired owner {retired_id} archive has owner.person_id "
                f"{archived_person_id!r}"
            )
        archive_paths[retired_id] = archive_path
    return archive_paths
