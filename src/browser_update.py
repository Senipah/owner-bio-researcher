from __future__ import annotations

from collections.abc import Callable
from typing import Any

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .constants import DEFAULT_TIMEOUT_SECONDS, RICH_TEXT_DETAIL_FIELDS
from .diffing import field_value, normalize_rich_text_html
from .tags import normalize_tag_name


class BrowserUpdateError(RuntimeError):
    pass


def _html_difference_summary(expected: str, actual: str) -> str:
    mismatch = next(
        (
            index
            for index, (expected_char, actual_char) in enumerate(
                zip(expected, actual, strict=False)
            )
            if expected_char != actual_char
        ),
        min(len(expected), len(actual)),
    )
    start = max(0, mismatch - 12)
    end = mismatch + 12
    return (
        f"expected length {len(expected)}, actual length {len(actual)}, "
        f"first difference at {mismatch}: "
        f"expected {expected[start:end]!r}, actual {actual[start:end]!r}"
    )


class OwnerBrowserUpdater:
    def __init__(self, driver, *, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.driver = driver
        self.wait = WebDriverWait(driver, timeout)

    def _open_overlay(self, profile_url: str, link_selector: str, form_selector: str):
        self.driver.switch_to.default_content()
        self.driver.get(profile_url)
        link = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, link_selector))
        )
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", link
        )
        try:
            link.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", link)

        iframe = self.wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "iframe.dfOverlayIframe")
            )
        )
        self.driver.switch_to.frame(iframe)
        return self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, form_selector))
        )

    def _dispatch_change(self, element) -> None:
        self.driver.execute_script(
            """
            arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
            arguments[0].dispatchEvent(new Event('change', {bubbles: true}));
            """,
            element,
        )

    @staticmethod
    def _is_detached(element) -> bool:
        try:
            element.is_enabled()
            return False
        except (NoSuchElementException, StaleElementReferenceException):
            return True

    def _set_detail_field(self, key: str, desired_field: dict[str, Any]) -> None:
        name = f"editpersondetails[{key}]"
        kind = desired_field.get("kind", "text")
        value = field_value(desired_field)
        elements = self.driver.find_elements(By.NAME, name)
        if not elements:
            raise BrowserUpdateError(f"Details control was not found: {name}")

        if kind == "radio":
            target = next(
                (
                    element
                    for element in elements
                    if str(element.get_attribute("value")) == str(value)
                ),
                None,
            )
            if target is None:
                raise BrowserUpdateError(
                    f"Radio option {value!r} was not found for {name}"
                )
            if not target.is_selected():
                self.driver.execute_script("arguments[0].click();", target)
            self._dispatch_change(target)
            return

        element = elements[0]
        if kind == "select":
            selector = Select(element)
            if value in ("", None):
                selector.select_by_value("")
            else:
                try:
                    selector.select_by_visible_text(str(value))
                except Exception:
                    option_id = desired_field.get("option_id")
                    if option_id is None:
                        raise
                    selector.select_by_value(str(option_id))
            self._dispatch_change(element)
            return

        if kind == "checkbox":
            should_select = bool(value)
            if element.is_selected() != should_select:
                self.driver.execute_script("arguments[0].click();", element)
            self._dispatch_change(element)
            return

        if kind == "rich_text_html" or key in RICH_TEXT_DETAIL_FIELDS:
            element_id = element.get_attribute("id")
            desired_value = "" if value is None else str(value)
            try:
                editor_available = self.wait.until(
                    lambda driver: driver.execute_script(
                        """
                        const id = arguments[0];
                        return Boolean(
                            window.CKEDITOR && CKEDITOR.instances[id]
                        );
                        """,
                        element_id,
                    )
                )
            except TimeoutException:
                editor_available = False

            if editor_available:
                result = self.driver.execute_async_script(
                    """
                    const id = arguments[0];
                    const value = arguments[1];
                    const done = arguments[arguments.length - 1];
                    const editor = window.CKEDITOR && CKEDITOR.instances[id];
                    if (!editor) {
                        done({updated: false, error: 'CKEditor not found'});
                        return;
                    }
                    try {
                        editor.setData(value, {
                            callback: function() {
                                try {
                                    editor.updateElement();
                                    done({
                                        updated: true,
                                        actual: editor.getData()
                                    });
                                } catch (error) {
                                    done({
                                        updated: false,
                                        error: String(error)
                                    });
                                }
                            }
                        });
                    } catch (error) {
                        done({updated: false, error: String(error)});
                    }
                    """,
                    element_id,
                    desired_value,
                )
                if not isinstance(result, dict) or not result.get("updated"):
                    error = (
                        result.get("error")
                        if isinstance(result, dict)
                        else "no result returned"
                    )
                    raise BrowserUpdateError(
                        f"CKEditor update failed for {name}: {error}"
                    )
                actual_value = str(result.get("actual", ""))
                if normalize_rich_text_html(actual_value) != (
                    normalize_rich_text_html(desired_value)
                ):
                    raise BrowserUpdateError(
                        f"CKEditor normalized the requested value for {name}: "
                        f"{_html_difference_summary(desired_value, actual_value)}"
                    )
            else:
                self.driver.execute_script(
                    """
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(
                        new Event('input', {bubbles: true})
                    );
                    arguments[0].dispatchEvent(
                        new Event('change', {bubbles: true})
                    );
                    """,
                    element,
                    desired_value,
                )
            return

        self.driver.execute_script(
            """
            arguments[0].removeAttribute('disabled');
            arguments[0].removeAttribute('readonly');
            arguments[0].value = '';
            """,
            element,
        )
        if value not in ("", None):
            element.send_keys(str(value))
        self._dispatch_change(element)

    def update_details(
        self,
        *,
        profile_url: str,
        changes: list[dict[str, Any]],
    ) -> None:
        form = self._open_overlay(
            profile_url,
            (
                "a.editButton.jsOverlayIframe"
                "[href*='/vessel/owners/person/edit/details.htm']"
            ),
            "form[name='editpersondetails']",
        )
        change_map = {item["field"]: item for item in changes}
        controlling_fields = ("unknown_name", "mortality_status")
        ordered_keys = [
            key for key in controlling_fields if key in change_map
        ] + [key for key in change_map if key not in controlling_fields]
        for key in ordered_keys:
            self._set_detail_field(key, change_map[key]["desired_field"])

        save = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.save"))
        )
        try:
            save.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", save)
        try:
            self.wait.until(lambda _driver: self._is_detached(form))
        finally:
            self.driver.switch_to.default_content()

    def _tag_rows(self):
        return [
            row
            for row in self.driver.find_elements(
                By.CSS_SELECTOR, "#jsTagRowContainer .jsTagRow"
            )
            if row.get_attribute("id") != "jsTagRowTemplate"
            and row.is_displayed()
        ]

    def _read_tag_rows(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for row in self._tag_rows():
            association_id = str(row.get_attribute("data-id") or "").strip()
            name = row.find_element(By.CSS_SELECTOR, ".jsTagText").text.strip()
            if not association_id or not name:
                raise BrowserUpdateError(
                    "A visible tag row had no association ID or name"
                )
            result.append({"association_id": association_id, "name": name})
        return result

    @staticmethod
    def _tag_state_signature(
        tags: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        return sorted(
            (
                str(item.get("association_id", "")),
                normalize_tag_name(str(item.get("name", ""))),
            )
            for item in tags
        )

    def _add_tag(self, name: str) -> dict[str, str]:
        normalized = normalize_tag_name(name)
        if any(
            normalize_tag_name(item["name"]) == normalized
            for item in self._read_tag_rows()
        ):
            raise BrowserUpdateError(f"Tag to add is already present: {name}")

        tag_input = self.wait.until(
            EC.visibility_of_element_located((By.ID, "tag"))
        )
        tag_input.clear()
        tag_input.send_keys(name)
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".jsAddTag"))
        )
        try:
            add_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", add_button)

        def added(_driver):
            return next(
                (
                    item
                    for item in self._read_tag_rows()
                    if normalize_tag_name(item["name"]) == normalized
                ),
                False,
            )

        try:
            result = self.wait.until(added)
        except TimeoutException as exc:
            raise BrowserUpdateError(f"Tag was not added: {name}") from exc
        return result

    def _delete_tag(self, removal: dict[str, Any]) -> dict[str, str]:
        association_id = str(removal.get("association_id", ""))
        expected_name = str(removal.get("name", ""))
        row = next(
            (
                candidate
                for candidate in self._tag_rows()
                if str(candidate.get_attribute("data-id") or "")
                == association_id
            ),
            None,
        )
        if row is None:
            raise BrowserUpdateError(
                f"Tag association to remove was not present: {association_id}"
            )
        actual_name = row.find_element(By.CSS_SELECTOR, ".jsTagText").text.strip()
        if normalize_tag_name(actual_name) != normalize_tag_name(expected_name):
            raise BrowserUpdateError(
                "Tag association changed before removal: "
                f"expected {expected_name!r}, found {actual_name!r}"
            )
        delete_link = row.find_element(By.CSS_SELECTOR, ".jsDeleteTag")
        try:
            delete_link.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", delete_link)
        remove_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    (
                        "//*[@id='jsDialogConfirm']/ancestor::div"
                        "[contains(@class,'ui-dialog')]"
                        "//button[normalize-space()='Remove']"
                    ),
                )
            )
        )
        try:
            remove_button.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", remove_button)
        try:
            self.wait.until(lambda _driver: self._is_detached(row))
        except TimeoutException as exc:
            raise BrowserUpdateError(
                f"Tag was not removed: {expected_name}"
            ) from exc
        return {"association_id": association_id, "name": actual_name}

    def update_tags(
        self,
        *,
        profile_url: str,
        expected_live: list[dict[str, Any]],
        additions: list[dict[str, Any]],
        removals: list[dict[str, Any]],
        on_operation: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        root = self._open_overlay(
            profile_url,
            (
                "a.editButton.jsOverlayIframe"
                "[href*='/base-entity/edit/tags.htm']"
            ),
            "#jsTagRowContainer",
        )
        try:
            opened_live = self._read_tag_rows()
            if self._tag_state_signature(opened_live) != self._tag_state_signature(
                expected_live
            ):
                raise BrowserUpdateError(
                    "Live tags changed between planning and opening the edit overlay"
                )

            for addition in additions:
                added = self._add_tag(str(addition["name"]))
                if on_operation is not None:
                    on_operation(
                        {
                            "action": "add",
                            "requested_name": str(addition["name"]),
                            "live": added,
                        }
                    )
            for removal in removals:
                removed = self._delete_tag(removal)
                if on_operation is not None:
                    on_operation(
                        {
                            "action": "remove",
                            "reason": removal.get("reason"),
                            "live": removed,
                        }
                    )

            done = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.save"))
            )
            try:
                done.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", done)
            self.wait.until(lambda _driver: self._is_detached(root))
        finally:
            self.driver.switch_to.default_content()

    def _social_rows(self):
        return [
            row
            for row in self.driver.find_elements(
                By.CSS_SELECTOR, "#jsSocialMediaLinkList .jsSocialMediaLink"
            )
            if row.get_attribute("id") != "jsSocialMediaLinkTemplate"
            and row.is_displayed()
        ]

    def _find_social_row(self, profile: dict[str, Any]):
        target_type = str(profile.get("type_id", ""))
        target_url = str(profile.get("url", ""))
        for row in self._social_rows():
            type_nodes = row.find_elements(
                By.CSS_SELECTOR, "input[name^='social_media_type_']"
            )
            url_nodes = row.find_elements(
                By.CSS_SELECTOR, "input[name^='social_media_url_']"
            )
            if (
                type_nodes
                and url_nodes
                and str(type_nodes[0].get_attribute("value")) == target_type
                and str(url_nodes[0].get_attribute("value")) == target_url
            ):
                return row
        return None

    def _delete_social(self, profile: dict[str, Any]) -> None:
        row = self._find_social_row(profile)
        if row is None:
            raise BrowserUpdateError(
                "Social profile to remove was not present: "
                f"{profile.get('type')} {profile.get('url')}"
            )
        delete_link = row.find_element(By.CSS_SELECTOR, "a.jsDelete")
        deleted_content = delete_link.find_element(By.XPATH, "ancestor::table[1]")
        self.driver.execute_script(
            "jQuery(arguments[0]).trigger('click');",
            delete_link,
        )
        delete_button = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    (
                        "//div[contains(@class,'ui-dialog') "
                        "and .//*[@id='jsDeleteMediaLinkInfo']]"
                        "//button[normalize-space()='Delete']"
                    ),
                )
            )
        )
        self.driver.execute_script(
            "jQuery(arguments[0]).trigger('click');",
            delete_button,
        )
        self.wait.until(lambda _driver: self._is_detached(deleted_content))

    def _add_social(self, profile: dict[str, Any]) -> None:
        type_select = self.driver.find_element(By.ID, "jsSocialMediaTypeId")
        url_input = self.driver.find_element(By.ID, "jsSocialMediaUrl")
        Select(type_select).select_by_value(str(profile.get("type_id", "")))
        self._dispatch_change(type_select)
        url_input.clear()
        url_input.send_keys(str(profile.get("url", "")))
        before = len(self._social_rows())
        self.driver.find_element(By.ID, "jsAddSocialMediaLink").click()
        self.wait.until(lambda _driver: len(self._social_rows()) == before + 1)

    def update_socials(
        self,
        *,
        profile_url: str,
        additions: list[dict[str, Any]],
        replacements: list[dict[str, Any]],
        removals: list[dict[str, Any]],
    ) -> None:
        form = self._open_overlay(
            profile_url,
            (
                "a.editButton.jsOverlayIframe"
                "[href*='/base-entity/edit/social.htm']"
            ),
            "form[name='socialForm']",
        )
        for replacement in replacements:
            self._delete_social(replacement["from"])
            self._add_social(replacement["to"])
        for profile in removals:
            self._delete_social(profile)
        for profile in additions:
            self._add_social(profile)

        save = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.save"))
        )
        try:
            save.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", save)
        try:
            self.wait.until(lambda _driver: self._is_detached(form))
        finally:
            self.driver.switch_to.default_content()

    def save_screenshot(self, path: str) -> None:
        self.driver.switch_to.default_content()
        self.driver.save_screenshot(path)
