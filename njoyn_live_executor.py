"""Non-submitting live executor contract for known CGI/Njoyn application pages."""
from __future__ import annotations

from typing import Protocol

from answer_map_executor import execute_known_page


class NjoynKnownPage(Protocol):
    def fill_known_page(self, answers: dict[str, str]) -> None: ...

    def read_value(self, selector: str) -> str: ...

    def read_parser_repairs(self) -> list[str]: ...


def execute_non_submitting_njoyn(
    *, plan: dict[str, object], page: NjoynKnownPage, known_answers: dict[str, str]
) -> dict[str, object]:
    """Batch known answers, verify repairs, and always stop before submit."""
    if plan.get("platform") != "njoyn":
        raise ValueError("Njoyn executor requires an njoyn handler plan")
    if plan.get("submission_enabled") is not False:
        raise ValueError("Njoyn live execution requires submission_enabled: false")

    answer_evidence = execute_known_page(page, known_answers)
    required = plan.get("parser_mismatches", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError("Njoyn handler plan has invalid parser mismatch evidence")
    recorded = page.read_parser_repairs()
    parser_repair_evidence = {
        "required_corrections": required,
        "recorded_corrections": recorded,
        "verified": set(required) <= set(recorded),
    }
    status = (
        "ready_for_human_review"
        if answer_evidence["verified"] and parser_repair_evidence["verified"]
        else "blocked"
    )
    return {
        "platform": "njoyn",
        "submission_enabled": False,
        "answer_evidence": answer_evidence,
        "parser_repair_evidence": parser_repair_evidence,
        "status": status,
        "next_action": "stop_before_submit",
    }
