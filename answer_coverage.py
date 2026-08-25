"""Fail-closed answer coverage preflight for non-submitting ATS plans."""
from __future__ import annotations

from question_engine import QuestionAnswerEngine


def build_coverage_matrix(
    *,
    profile: dict,
    questions: list[dict],
    google_doc_answers: list[dict] | None = None,
    company: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Report profile- and company-answer-backed questions without answer values."""
    engine = QuestionAnswerEngine(profile=profile, google_doc_answers=google_doc_answers)
    matrix: dict[str, list[dict[str, str]]] = {
        "known": [],
        "company_specific": [],
        "optional_skip": [],
        "human_required": [],
    }
    for item in questions:
        result = engine.answer(item["label"], company=company)
        if result.status == "answered":
            bucket = "company_specific" if result.source == "google_doc:company" else "known"
            matrix[bucket].append(
                {
                    "question": item["label"],
                    "question_key": result.question_key or "unknown",
                    "source": result.source or "unknown",
                }
            )
        else:
            entry = {
                "question": item["label"],
                "question_key": result.question_key or "unknown",
            }
            if item.get("required", False):
                entry["reason"] = result.reason or "unknown_question"
                matrix["human_required"].append(entry)
            else:
                matrix["optional_skip"].append(entry)
    return matrix
