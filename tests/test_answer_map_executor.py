from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import answer_map_executor


class InMemoryKnownPage:
    """One bounded page-operation seam with deterministic read-back."""

    def __init__(self) -> None:
        self.values = {"#first-name": "", "#last-name": ""}
        self.operations: list[dict[str, str]] = []

    def fill_known_page(self, answers: dict[str, str]) -> None:
        self.operations.append(dict(answers))
        self.values.update(answers)

    def read_value(self, selector: str) -> str:
        return self.values[selector]


def test_execute_known_page_fills_answer_map_once_and_returns_field_read_back_evidence():
    page = InMemoryKnownPage()

    result = answer_map_executor.execute_known_page(
        page,
        {"#first-name": "Kevin", "#last-name": "Pyo"},
    )

    assert page.operations == [{"#first-name": "Kevin", "#last-name": "Pyo"}]
    assert result == {
        "action": "fill_known_page",
        "field_evidence": [
            {
                "selector": "#first-name",
                "expected": "Kevin",
                "actual": "Kevin",
                "verified": True,
            },
            {
                "selector": "#last-name",
                "expected": "Pyo",
                "actual": "Pyo",
                "verified": True,
            },
        ],
        "verified": True,
    }
