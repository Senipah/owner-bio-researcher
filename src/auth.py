from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import requests

from .constants import DEFAULT_TIMEOUT_SECONDS, HTTP_TIMEOUT_SECONDS, LOGIN_URL
from .parsers import is_login_page
from .user_secrets import load_user_credentials


class AuthenticationError(RuntimeError):
    pass


@dataclass
class AuthenticatedContext:
    driver: object
    session: requests.Session


def load_credentials() -> tuple[str, str]:
    load_user_credentials()
    username = os.getenv("SYN_USER", "")
    password = os.getenv("SYN_PASS", "")
    if not username or not password:
        raise AuthenticationError(
            "SYN credentials were not loaded by src.user_secrets"
        )
    return username, password


def create_driver(*, headless: bool = False):
    from seleniumbase import Driver

    return Driver(uc=True, headless=headless)


def syn_login(driver, *, username: str, password: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#LoginForm"))
        )
    except Exception:
        if "agent.superyachtnetwork.com" not in (driver.current_url or ""):
            raise AuthenticationError(
                f"Unexpected page while checking login: {driver.current_url}"
            )
        return

    user_element = driver.find_element(By.CSS_SELECTOR, "#LoginFormUsername")
    password_element = driver.find_element(By.CSS_SELECTOR, "#LoginFormPassword")
    login_button = driver.find_element(By.CSS_SELECTOR, "#LoginButton")
    user_element.clear()
    user_element.send_keys(username)
    password_element.clear()
    password_element.send_keys(password)

    try:
        keep_nodes = driver.find_elements(By.CSS_SELECTOR, "#LoginFormKeepLogin")
        if keep_nodes and not keep_nodes[0].is_selected():
            try:
                keep_nodes[0].click()
            except Exception:
                driver.execute_script(
                    """
                    const checkbox = arguments[0];
                    checkbox.checked = true;
                    checkbox.dispatchEvent(new Event('change', {bubbles: true}));
                    """,
                    keep_nodes[0],
                )
    except Exception:
        pass

    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#LoginButton"))
        ).click()
    except Exception:
        driver.execute_script("arguments[0].click();", login_button)

    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT_SECONDS).until_not(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#LoginForm"))
        )
    except Exception as exc:
        raise AuthenticationError("Login form did not close after submission") from exc


def requests_session_from_driver(driver) -> requests.Session:
    session = requests.Session()
    try:
        user_agent = driver.execute_script("return navigator.userAgent")
    except Exception:
        user_agent = None
    if user_agent:
        session.headers["User-Agent"] = str(user_agent)
    session.headers["Accept"] = "text/html,application/xhtml+xml"
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )
    return session


def fetch_html(
    session: requests.Session,
    url: str,
    *,
    expected_marker: str | None = None,
) -> str:
    response = session.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    html = response.text
    if is_login_page(html):
        raise AuthenticationError(
            "The authenticated session expired and returned the login page"
        )
    if expected_marker and expected_marker not in html:
        raise RuntimeError(
            f"Expected page marker {expected_marker!r} was not found at {url}"
        )
    return html


@contextmanager
def authenticated_context(*, headless: bool = False) -> Iterator[AuthenticatedContext]:
    username, password = load_credentials()
    driver = create_driver(headless=headless)
    try:
        syn_login(driver, username=username, password=password)
        session = requests_session_from_driver(driver)
        yield AuthenticatedContext(driver=driver, session=session)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
