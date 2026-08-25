from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import browser_actions


class InMemoryPage:
    """Deterministic page seam used to verify browser action contracts."""

    def __init__(self) -> None:
        self.values = {"#first-name": "Old value"}
        self.operations: list[tuple[str, str, str]] = []

    def replace_text(self, selector: str, value: str) -> None:
        self.operations.append(("replace_text", selector, value))
        self.values[selector] = value

    def read_value(self, selector: str) -> str:
        return self.values[selector]


def test_replace_text_returns_exact_post_action_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.replace_text(page, "#first-name", "Kevin")

    assert page.operations == [("replace_text", "#first-name", "Kevin")]
    assert evidence == {
        "action": "replace_text",
        "selector": "#first-name",
        "expected": "Kevin",
        "actual": "Kevin",
        "verified": True,
    }
