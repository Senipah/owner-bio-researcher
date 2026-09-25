from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.owner_identity import (
    load_owner_identity_resolutions,
    owner_identity_redirects,
    validate_owner_identity_archives,
)


def _write_registry(path: Path, resolutions: list[dict]) -> None:
    path.write_text(
        json.dumps({"schema_version": 1, "resolutions": resolutions}),
        encoding="utf-8",
    )


def _resolution(retired: int, canonical: int) -> dict:
    return {
        "status": "merged_duplicate",
        "retired_person_id": retired,
        "canonical_person_id": canonical,
        "archive_path": f"archive/{retired}.research.json",
        "recorded_on": "2026-09-25",
        "note": "Reviewed duplicate merge.",
    }


def test_loads_reviewed_duplicate_redirect(tmp_path: Path) -> None:
    path = tmp_path / "resolutions.json"
    _write_registry(path, [_resolution(3192, 529)])

    resolutions = load_owner_identity_resolutions(path)

    assert owner_identity_redirects(resolutions) == {3192: 529}
    assert resolutions[3192].archive_path == "archive/3192.research.json"


def test_rejects_duplicate_retired_id(tmp_path: Path) -> None:
    path = tmp_path / "resolutions.json"
    _write_registry(path, [_resolution(3192, 529), _resolution(3192, 500)])

    with pytest.raises(ValueError, match="duplicate retired_person_id"):
        load_owner_identity_resolutions(path)


def test_rejects_redirect_chain(tmp_path: Path) -> None:
    path = tmp_path / "resolutions.json"
    _write_registry(path, [_resolution(3192, 529), _resolution(529, 500)])

    with pytest.raises(ValueError, match="directly to active canonical IDs"):
        load_owner_identity_resolutions(path)


def test_validates_archived_dossier_identity(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "3192.research.json"
    archive.parent.mkdir()
    archive.write_text(
        json.dumps({"owner": {"person_id": 3192}}),
        encoding="utf-8",
    )
    path = tmp_path / "resolutions.json"
    resolution = _resolution(3192, 529)
    resolution["archive_path"] = "archive/3192.research.json"
    _write_registry(path, [resolution])
    resolutions = load_owner_identity_resolutions(path)

    archive_paths = validate_owner_identity_archives(
        resolutions,
        repository_root=tmp_path,
    )

    assert archive_paths == {3192: archive}


def test_rejects_archive_for_different_owner(tmp_path: Path) -> None:
    archive = tmp_path / "archive" / "3192.research.json"
    archive.parent.mkdir()
    archive.write_text(
        json.dumps({"owner": {"person_id": 529}}),
        encoding="utf-8",
    )
    path = tmp_path / "resolutions.json"
    resolution = _resolution(3192, 529)
    resolution["archive_path"] = "archive/3192.research.json"
    _write_registry(path, [resolution])

    with pytest.raises(ValueError, match="has owner.person_id 529"):
        validate_owner_identity_archives(
            load_owner_identity_resolutions(path),
            repository_root=tmp_path,
        )
