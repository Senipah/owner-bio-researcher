from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

from src.browser_update import OwnerBrowserUpdater


class _FakeElement:
    def get_attribute(self, name: str) -> str | None:
        if name == "id":
            return "EditpersondetailsInternalNotes"
        return None

    def send_keys(self, _value: str) -> None:
        raise AssertionError("Rich-text fields must not use send_keys")


class _FakeDriver:
    def __init__(self) -> None:
        self.element = _FakeElement()
        self.scripts: list[str] = []

    def find_elements(self, _by: str, _value: str) -> list[_FakeElement]:
        return [self.element]

    def execute_script(self, script: str, *_args: object) -> bool:
        self.scripts.append(script)
        return "CKEDITOR.instances" in script


def test_known_rich_text_field_uses_ckeditor_for_legacy_textarea_kind() -> None:
    driver = _FakeDriver()
    updater = OwnerBrowserUpdater(driver)

    updater._set_detail_field(
        "internal_notes",
        {"kind": "textarea", "value": "<p>Updated</p>"},
    )

    assert len(driver.scripts) == 1
    assert "CKEDITOR.instances" in driver.scripts[0]


class _ElementState:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def is_enabled(self) -> bool:
        if self.error is not None:
            raise self.error
        return True


@pytest.mark.parametrize(
    "error",
    [NoSuchElementException(), StaleElementReferenceException()],
)
def test_detached_element_accepts_chrome_element_loss_errors(
    error: Exception,
) -> None:
    assert OwnerBrowserUpdater._is_detached(_ElementState(error))


def test_attached_element_is_not_detached() -> None:
    assert not OwnerBrowserUpdater._is_detached(_ElementState())
