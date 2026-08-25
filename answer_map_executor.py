"""Bounded, verification-first execution of complete known-page answer maps."""
from __future__ import annotations

from typing import Protocol


class KnownPage(Protocol):
    def fill_known_page(self, answers: dict[str, str]) -> None: ...

    def read_value(self, selector: str) -> str: ...


def execute_known_page(page: KnownPage, answers: dict[str, str]) -> dict[str, object]:
    """Fill one complete known page once and return per-field read-back evidence."""
    page.fill_known_page(answers)
    field_evidence = []
    for selector, expected in answers.items():
        actual = page.read_value(selector)
        field_evidence.append(
            {
                "selector": selector,
                "expected": expected,
                "actual": actual,
                "verified": actual == expected,
            }
        )
    return {
        "action": "fill_known_page",
        "field_evidence": field_evidence,
        "verified": all(item["verified"] for item in field_evidence),
    }
