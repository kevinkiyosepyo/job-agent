"""Deterministic, verification-first browser action contracts."""
from __future__ import annotations

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
