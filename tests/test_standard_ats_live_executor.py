from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("platform", ["workday", "greenhouse", "lever", "oracle"])
def test_standard_executor_batches_known_answers_and_stops_before_submit(platform: str):
    import standard_ats_live_executor

    class Page:
        def __init__(self) -> None:
            self.values = {"#name": ""}
            self.answer_batches: list[dict[str, str]] = []
            self.submit_calls = 0

        def fill_known_page(self, answers: dict[str, str]) -> None:
            self.answer_batches.append(dict(answers))
            self.values.update(answers)

        def read_value(self, selector: str) -> str:
            return self.values[selector]

        def submit(self) -> None:
            self.submit_calls += 1

    page = Page()
    result = standard_ats_live_executor.execute_non_submitting_standard_ats(
        plan={"platform": platform, "submission_enabled": False},
        page=page,
        known_answers={"#name": "Kevin Pyo"},
    )

    assert page.answer_batches == [{"#name": "Kevin Pyo"}]
    assert page.submit_calls == 0
    assert result == {
        "platform": platform,
        "submission_enabled": False,
        "answer_evidence": {
            "action": "fill_known_page",
            "field_evidence": [
                {"selector": "#name", "expected": "Kevin Pyo", "actual": "Kevin Pyo", "verified": True}
            ],
            "verified": True,
        },
        "status": "ready_for_human_review",
        "next_action": "stop_before_submit",
    }
