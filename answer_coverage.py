"""Fail-closed answer coverage preflight for non-submitting ATS plans."""
from __future__ import annotations

from question_engine import QuestionAnswerEngine


def _native_option_reason(item: dict, answer: str | None) -> str | None:
    """A known fact still needs one explicit option; this is never bound-state proof."""
    if item.get("type") == "checkbox":
        return "checkbox_selection_unverified"
    if item.get("type") == "combobox":
        return "combobox_options_unverified"
    if "native_select" not in item and "native_radio" not in item:
        return None
    if "native_radio" in item:
        group = item["native_radio"]
        if (not isinstance(group, dict) or group.get("source") != "static_html"
                or group.get("type") != "radio"):
            return "native_option_inventory_unavailable"
    else:
        group = item["native_select"]
        if not isinstance(group, dict) or group.get("source") != "static_html":
            return "native_option_inventory_unavailable"
        if group.get("multiple") is not False or group.get("disabled") is not False:
            return "native_select_not_supported"
    options = group.get("options")
    if (not isinstance(options, list) or not options or any(
        not isinstance(option, dict) or not isinstance(option.get("label"), str)
        or not isinstance(option.get("value"), str) or not isinstance(option.get("disabled"), bool)
        for option in options
    )):
        return "native_option_inventory_unavailable"
    matches = [option for option in options if option.get("label") == answer]
    if len(matches) != 1:
        return "answer_not_in_native_options"
    option = matches[0]
    value = option.get("value")
    if (option.get("disabled") is not False or not isinstance(value, str) or not value.strip()
        or sum(other.get("value") == value for other in options) != 1):
        return "native_option_not_selectable"
    return None


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
        option_reason = _native_option_reason(item, result.answer) if result.status == "answered" else None
        if result.status == "answered" and option_reason is None:
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
                entry["reason"] = option_reason or result.reason or "unknown_question"
                matrix["human_required"].append(entry)
            else:
                matrix["optional_skip"].append(entry)
    return matrix
