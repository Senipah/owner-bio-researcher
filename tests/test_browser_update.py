from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

from src import browser_update
from src.browser_update import BrowserUpdateError, OwnerBrowserUpdater


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


class _SelectOption:
    def __init__(self, value: str, text: str) -> None:
        self.value = value
        self.text = text

    def get_attribute(self, name: str) -> str | None:
        return self.value if name == "value" else None


class _FallbackSelect:
    def __init__(self, options: list[_SelectOption]) -> None:
        self.options = options
        self.selected_value: str | None = None

    def select_by_visible_text(self, _value: str) -> None:
        raise NoSuchElementException()

    def select_by_value(self, value: str) -> None:
        self.selected_value = value


def test_select_fallback_rejects_stale_option_id(monkeypatch) -> None:
    driver = _FakeDriver()
    selector = _FallbackSelect([_SelectOption("", "Select")])
    monkeypatch.setattr(browser_update, "Select", lambda _element: selector)
    updater = OwnerBrowserUpdater(driver)

    with pytest.raises(BrowserUpdateError, match="maps to 'Select'"):
        updater._set_detail_field(
            "nationality",
            {
                "kind": "select",
                "value": "Canada",
                "option_id": "",
            },
        )

    assert selector.selected_value is None


def test_select_fallback_accepts_matching_option_id(monkeypatch) -> None:
    driver = _FakeDriver()
    selector = _FallbackSelect([_SelectOption("29", "Canadian")])
    monkeypatch.setattr(browser_update, "Select", lambda _element: selector)
    updater = OwnerBrowserUpdater(driver)

    updater._set_detail_field(
        "nationality",
        {
            "kind": "select",
            "value": "Canadian",
            "option_id": "29",
        },
    )

    assert selector.selected_value == "29"


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


def test_tag_state_signature_uses_association_id_and_normalized_name() -> None:
    left = [
        {"association_id": "2", "name": "Oil and gas"},
        {"association_id": "1", "name": "Luxury goods"},
    ]
    right = list(reversed([
        {"association_id": "1", "name": "Luxury goods"},
        {"association_id": "2", "name": "Oil & gas"},
    ]))

    assert OwnerBrowserUpdater._tag_state_signature(left) == (
        OwnerBrowserUpdater._tag_state_signature(right)
    )


class _SwitchTo:
    def __init__(self) -> None:
        self.default_count = 0

    def default_content(self) -> None:
        self.default_count += 1


class _TagDriver:
    def __init__(self) -> None:
        self.switch_to = _SwitchTo()


def test_update_tags_stops_if_overlay_state_changed() -> None:
    updater = object.__new__(OwnerBrowserUpdater)
    updater.driver = _TagDriver()
    updater._open_overlay = lambda *_args, **_kwargs: object()
    updater._read_tag_rows = lambda: [
        {"association_id": "2", "name": "Changed"}
    ]

    with pytest.raises(RuntimeError, match="changed between planning"):
        updater.update_tags(
            profile_url="https://example.test/owner/1",
            expected_live=[{"association_id": "1", "name": "Original"}],
            additions=[{"name": "Valve"}],
            removals=[],
        )

    assert updater.driver.switch_to.default_count == 1


class _Done:
    def click(self) -> None:
        return None


class _ImmediateWait:
    def until(self, _condition):
        return _Done()


def test_update_tags_adds_before_removing_and_reports_each_operation() -> None:
    updater = object.__new__(OwnerBrowserUpdater)
    updater.driver = _TagDriver()
    updater.wait = _ImmediateWait()
    updater._open_overlay = lambda *_args, **_kwargs: object()
    updater._read_tag_rows = lambda: [
        {"association_id": "1", "name": "Old tag"}
    ]
    sequence: list[tuple[str, str]] = []
    updater._add_tag = lambda name: (
        sequence.append(("add", name))
        or {"association_id": "2", "name": name}
    )
    updater._delete_tag = lambda removal: (
        sequence.append(("remove", removal["name"]))
        or {
            "association_id": removal["association_id"],
            "name": removal["name"],
        }
    )
    operations: list[dict] = []

    updater.update_tags(
        profile_url="https://example.test/owner/1",
        expected_live=[{"association_id": "1", "name": "Old tag"}],
        additions=[{"name": "New tag"}],
        removals=[
            {
                "association_id": "1",
                "name": "Old tag",
                "reason": "not_in_desired_dossier_tags",
            }
        ],
        on_operation=operations.append,
    )

    assert sequence == [("add", "New tag"), ("remove", "Old tag")]
    assert [operation["action"] for operation in operations] == [
        "add",
        "remove",
    ]
    assert updater.driver.switch_to.default_count == 1
