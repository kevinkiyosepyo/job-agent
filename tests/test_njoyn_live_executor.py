from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_njoyn_executor_batches_answers_verifies_parser_repairs_and_stops_before_submit():
    import njoyn_live_executor

    class Page:
        def __init__(self) -> None:
            self.values = {"#first-name": "", "#last-name": ""}
            self.answer_batches: list[dict[str, str]] = []
            self.submit_calls = 0

        def fill_known_page(self, answers: dict[str, str]) -> None:
            self.answer_batches.append(dict(answers))
            self.values.update(answers)

        def read_value(self, selector: str) -> str:
            return self.values[selector]

        def read_parser_repairs(self) -> list[str]:
            return ["education"]

        def submit(self) -> None:
            self.submit_calls += 1

    page = Page()
    result = njoyn_live_executor.execute_non_submitting_njoyn(
        plan={
            "platform": "njoyn",
            "submission_enabled": False,
            "parser_mismatches": ["education"],
        },
        page=page,
        known_answers={"#first-name": "Kevin", "#last-name": "Pyo"},
    )

    assert page.answer_batches == [{"#first-name": "Kevin", "#last-name": "Pyo"}]
    assert page.submit_calls == 0
    assert result == {
        "platform": "njoyn",
        "submission_enabled": False,
        "answer_evidence": {
            "action": "fill_known_page",
            "field_evidence": [
                {"selector": "#first-name", "expected": "Kevin", "actual": "Kevin", "verified": True},
                {"selector": "#last-name", "expected": "Pyo", "actual": "Pyo", "verified": True},
            ],
            "verified": True,
        },
        "parser_repair_evidence": {
            "required_corrections": ["education"],
            "recorded_corrections": ["education"],
            "verified": True,
        },
        "status": "ready_for_human_review",
        "next_action": "stop_before_submit",
    }
