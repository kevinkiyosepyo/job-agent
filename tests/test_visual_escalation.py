from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_visual_escalation_retries_once_after_verified_dom_ax_failure():
    import visual_escalation

    calls: list[str] = []

    def dom_ax_attempt() -> dict[str, object]:
        calls.append("dom_ax")
        return {"verified": False, "reason": "control obscured"}

    def scoped_screenshot_ocr(reason: str) -> dict[str, object]:
        calls.append(f"ocr:{reason}")
        return {"scope": "exact-page-42", "text": "Continue"}

    def inspected_retry(ocr_evidence: dict[str, object]) -> dict[str, object]:
        calls.append(f"retry:{ocr_evidence['scope']}")
        return {"verified": True, "evidence": "selected social-media"}

    result = visual_escalation.execute_with_scoped_ocr_escalation(
        dom_ax_attempt,
        scoped_screenshot_ocr,
        inspected_retry,
    )

    assert calls == ["dom_ax", "ocr:control obscured", "retry:exact-page-42"]
    assert result == {
        "status": "completed",
        "dom_ax_attempts": 1,
        "scoped_screenshot_ocr_attempts": 1,
        "inspected_retries": 1,
        "evidence": "selected social-media",
    }


def test_visual_escalation_returns_stable_blocker_after_one_inspected_retry():
    import visual_escalation

    calls: list[str] = []

    def dom_ax_attempt() -> dict[str, object]:
        calls.append("dom_ax")
        return {"verified": False, "reason": "hidden option"}

    def scoped_screenshot_ocr(reason: str) -> dict[str, object]:
        calls.append(f"ocr:{reason}")
        return {"scope": "exact-page-42", "text": "No matching option"}

    def inspected_retry(ocr_evidence: dict[str, object]) -> dict[str, object]:
        calls.append(f"retry:{ocr_evidence['scope']}")
        return {"verified": False, "reason": "option remains unavailable"}

    result = visual_escalation.execute_with_scoped_ocr_escalation(
        dom_ax_attempt,
        scoped_screenshot_ocr,
        inspected_retry,
    )

    assert calls == ["dom_ax", "ocr:hidden option", "retry:exact-page-42"]
    assert result == {
        "status": "blocked",
        "blocker": "option remains unavailable",
        "dom_ax_attempts": 1,
        "scoped_screenshot_ocr_attempts": 1,
        "inspected_retries": 1,
    }
