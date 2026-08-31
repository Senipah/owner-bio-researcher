from __future__ import annotations

import json
from pathlib import Path

import pytest

from update_owners import load_biography_ignore_ids


def _write_config(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def test_load_biography_ignore_ids(tmp_path: Path) -> None:
    path = tmp_path / "ignore.json"
    _write_config(
        path,
        {"schema_version": 1, "person_ids": [8690, 42]},
    )

    assert load_biography_ignore_ids(path) == {42, 8690}


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"schema_version": 2, "person_ids": []},
        {"schema_version": 1, "person_ids": "8690"},
        {"schema_version": 1, "person_ids": [0]},
        {"schema_version": 1, "person_ids": [True]},
        {"schema_version": 1, "person_ids": [8690, 8690]},
    ],
)
def test_load_biography_ignore_ids_rejects_invalid_config(
    tmp_path: Path,
    document: object,
) -> None:
    path = tmp_path / "ignore.json"
    _write_config(path, document)

    with pytest.raises(ValueError):
        load_biography_ignore_ids(path)
