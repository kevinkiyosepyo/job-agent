"""Shared non-submitting live executor for Workday, Greenhouse, Lever, and Oracle."""
from __future__ import annotations

from typing import Protocol

from answer_map_executor import execute_known_page


SUPPORTED_PLATFORMS = frozenset({"workday", "greenhouse", "lever", "oracle"})


class StandardKnownPage(Protocol):
    def fill_known_page(self, answers: dict[str, str]) -> None: ...

    def read_value(self, selector: str) -> str: ...


def execute_non_submitting_standard_ats(
    *, plan: dict[str, object], page: StandardKnownPage, known_answers: dict[str, str]
) -> dict[str, object]:
    """Batch approved answers using shared evidence and stop for human Review."""
    platform = plan.get("platform")
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("Standard live executor requires a supported ATS handler plan")
    if plan.get("submission_enabled") is not False:
        raise ValueError("Standard live execution requires submission_enabled: false")

    answer_evidence = execute_known_page(page, known_answers)
    return {
        "platform": platform,
        "submission_enabled": False,
        "answer_evidence": answer_evidence,
        "status": "ready_for_human_review" if answer_evidence["verified"] else "blocked",
        "next_action": "stop_before_submit",
    }
