"""Deterministic, verification-first browser action contracts."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TextPage(Protocol):
    def replace_text(self, selector: str, value: str) -> None: ...

    def read_value(self, selector: str) -> str: ...


class NativeSelectPage(Protocol):
    def select_option(self, selector: str, value: str) -> None: ...

    def read_selected_option(self, selector: str) -> str: ...


class CheckedPage(Protocol):
    def set_checked(self, selector: str, checked: bool) -> None: ...

    def read_checked(self, selector: str) -> bool: ...


class CDPUploadPage(Protocol):
    def cdp_upload(self, selector: str, path: str) -> None: ...

    def read_uploaded_filename(self, selector: str) -> str: ...


class ScrollClickPage(Protocol):
    def scroll_into_view(self, selector: str) -> None: ...

    def click(self, selector: str) -> None: ...

    def read_post_click_state(self, selector: str) -> str: ...


def replace_text(page: TextPage, selector: str, value: str) -> dict[str, object]:
    """Replace a field's text and return evidence from an exact read-back."""
    page.replace_text(selector, value)
    actual = page.read_value(selector)
    return {
        "action": "replace_text",
        "selector": selector,
        "expected": value,
        "actual": actual,
        "verified": actual == value,
    }


def native_select(page: NativeSelectPage, selector: str, value: str) -> dict[str, object]:
    """Select a native option and return evidence from selected-option read-back."""
    page.select_option(selector, value)
    actual = page.read_selected_option(selector)
    return {
        "action": "native_select",
        "selector": selector,
        "expected": value,
        "actual": actual,
        "verified": actual == value,
    }


def set_checked(page: CheckedPage, selector: str, checked: bool) -> dict[str, object]:
    """Set a radio or checkbox state and return checked-state read-back evidence."""
    page.set_checked(selector, checked)
    actual = page.read_checked(selector)
    return {
        "action": "set_checked",
        "selector": selector,
        "expected": checked,
        "actual": actual,
        "verified": actual == checked,
    }


def cdp_upload(page: CDPUploadPage, selector: str, path: str) -> dict[str, object]:
    """Attach one file through CDP and return filename read-back evidence."""
    expected = Path(path).name
    page.cdp_upload(selector, path)
    actual = page.read_uploaded_filename(selector)
    return {
        "action": "cdp_upload",
        "selector": selector,
        "expected": expected,
        "actual": actual,
        "verified": actual == expected,
    }


def scroll_and_click(
    page: ScrollClickPage, selector: str, expected_state: str
) -> dict[str, object]:
    """Scroll to a control, click it, and return post-click read-back evidence."""
    page.scroll_into_view(selector)
    page.click(selector)
    actual = page.read_post_click_state(selector)
    return {
        "action": "scroll_and_click",
        "selector": selector,
        "expected": expected_state,
        "actual": actual,
        "verified": actual == expected_state,
    }
