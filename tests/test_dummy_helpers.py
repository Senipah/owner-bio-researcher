from __future__ import annotations

from test_dummy_account import _dummy_notes_with_marker


def test_dummy_notes_marker_uses_ckeditor_canonical_paragraph() -> None:
    assert _dummy_notes_with_marker("", "marker") == "<p>marker</p>\r\n"


def test_dummy_notes_marker_separates_existing_html() -> None:
    assert _dummy_notes_with_marker(
        "<p>Existing</p>",
        "new & marker",
    ) == "<p>Existing</p>\r\n<p>new &amp; marker</p>\r\n"
