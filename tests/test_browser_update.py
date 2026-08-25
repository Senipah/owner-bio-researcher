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
    def __init__(self, *, actual: str = "<p>Updated</p>") -> None:
        self.element = _FakeElement()
        self.scripts: list[str] = []
        self.async_scripts: list[str] = []
        self.actual = actual

    def find_elements(self, _by: str, _value: str) -> list[_FakeElement]:
        return [self.element]

    def execute_script(self, script: str, *_args: object) -> bool:
        self.scripts.append(script)
        return "CKEDITOR.instances" in script

    def execute_async_script(self, script: str, *_args: object) -> dict:
        self.async_scripts.append(script)
        return {"updated": True, "actual": self.actual}


def test_known_rich_text_field_uses_ckeditor_for_legacy_textarea_kind() -> None:
    driver = _FakeDriver()
    updater = OwnerBrowserUpdater(driver)

    updater._set_detail_field(
        "internal_notes",
        {"kind": "textarea", "value": "<p>Updated</p>"},
    )

    assert len(driver.scripts) == 1
    assert "CKEDITOR.instances" in driver.scripts[0]
    assert len(driver.async_scripts) == 1
    assert "callback: function()" in driver.async_scripts[0]
    assert driver.async_scripts[0].index("callback: function()") < (
        driver.async_scripts[0].index("editor.updateElement()")
    )


def test_ckeditor_html_entities_are_accepted_as_equivalent() -> None:
    driver = _FakeDriver(actual="<p>J&oslash;rn Updated</p>")
    updater = OwnerBrowserUpdater(driver)

    updater._set_detail_field(
        "biography",
        {"kind": "rich_text_html", "value": "<p>Jørn Updated</p>"},
    )


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
