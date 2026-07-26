from __future__ import annotations

from src.io_utils import (
    atomic_write_json,
    load_json,
    new_document,
    new_owner,
)


def test_atomic_json_round_trip(tmp_path) -> None:
    document = new_document()
    document["owners"].append(
        new_owner(
            person_id=123,
            profile_url="https://example.test/person?id=123",
            report={"first_name": "Test"},
        )
    )
    path = tmp_path / "owners.json"

    atomic_write_json(path, document)

    assert load_json(path) == document
    assert not list(tmp_path.glob("*.tmp"))
