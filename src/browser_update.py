from __future__ import annotations

from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .constants import DEFAULT_TIMEOUT_SECONDS
from .diffing import field_value


class BrowserUpdateError(RuntimeError):
    pass


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

        if kind == "rich_text_html":
            element_id = element.get_attribute("id")
            updated = self.driver.execute_script(
                """
                const id = arguments[0];
                const value = arguments[1];
                if (window.CKEDITOR && CKEDITOR.instances[id]) {
                    CKEDITOR.instances[id].setData(value);
                    CKEDITOR.instances[id].updateElement();
                    return true;
                }
                return false;
                """,
                element_id,
                "" if value is None else str(value),
            )
            if not updated:
                self.driver.execute_script(
                    """
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(
                        new Event('change', {bubbles: true})
                    );
                    """,
                    element,
                    "" if value is None else str(value),
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
            self.wait.until(EC.staleness_of(form))
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
        row.find_element(By.CSS_SELECTOR, "a.jsDelete").click()
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
        delete_button.click()
        self.wait.until(EC.staleness_of(row))

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
            self.wait.until(EC.staleness_of(form))
        finally:
            self.driver.switch_to.default_content()

    def save_screenshot(self, path: str) -> None:
        self.driver.switch_to.default_content()
        self.driver.save_screenshot(path)
