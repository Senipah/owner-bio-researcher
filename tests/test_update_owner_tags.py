from __future__ import annotations

from update_owner_tags import _verification_succeeded


def _plan(*, additions: int = 0, removals: int = 0, conflicts: int = 0) -> dict:
    return {
        "additions": [{} for _ in range(additions)],
        "removals": [{} for _ in range(removals)],
        "conflicts": [{} for _ in range(conflicts)],
    }


def test_add_only_verification_allows_unremoved_live_extras() -> None:
    assert _verification_succeeded(
        _plan(removals=1),
        replace_tags=False,
    )


def test_exact_verification_requires_removals_to_be_complete() -> None:
    assert not _verification_succeeded(
        _plan(removals=1),
        replace_tags=True,
    )


def test_verification_never_accepts_missing_additions_or_conflicts() -> None:
    assert not _verification_succeeded(
        _plan(additions=1),
        replace_tags=False,
    )
    assert not _verification_succeeded(
        _plan(conflicts=1),
        replace_tags=False,
    )
