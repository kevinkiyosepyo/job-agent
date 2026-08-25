"""Deterministic, verification-first browser action contracts."""
from __future__ import annotations

from typing import Protocol


class TextPage(Protocol):
    def replace_text(self, selector: str, value: str) -> None: ...

    def read_value(self, selector: str) -> str: ...


class NativeSelectPage(Protocol):
    def select_option(self, selector: str, value: str) -> None: ...

    def read_selected_option(self, selector: str) -> str: ...


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
