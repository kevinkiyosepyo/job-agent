"""Deterministic, verification-first browser action contracts."""
from __future__ import annotations

from typing import Protocol


class TextPage(Protocol):
    def replace_text(self, selector: str, value: str) -> None: ...

    def read_value(self, selector: str) -> str: ...


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
