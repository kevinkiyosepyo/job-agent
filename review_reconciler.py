"""Authoritative, sanitized reconciliation of an ATS Review surface.

The reconciler is deliberately pure and non-submitting.  It compares exact
server-rendered state with independently supplied profile, resume, question,
repair, and target facts, but never returns the compared profile values or
resume hash.  Any difference remains explicitly human-required.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class ReviewEvidenceError(ValueError):
    """Review inputs were structurally invalid and cannot be authoritative."""


TARGET_KEYS = ("target_id", "page_url", "company", "role", "requisition")


def _require_dict(value: object, *, label: str) -> dict:
    if not isinstance(value, dict):
        raise ReviewEvidenceError(f"{label} must be an object")
    return value


def _binding(payload: dict) -> dict[str, object]:
    identity = _require_dict(payload.get("identity", {}), label="target identity")
    return {
        "target_id": payload.get("target_id"),
        "page_url": payload.get("page_url"),
        "company": identity.get("company"),
        "role": identity.get("role"),
        "requisition": identity.get("requisition"),
    }


def _add_once(human_required: list[dict[str, str]], item: dict[str, str]) -> None:
    if item not in human_required:
        human_required.append(item)


def _preparation_is_verified(preparation: dict, human_required: list[dict[str, str]]) -> None:
    evidence = _require_dict(preparation.get("evidence", {}), label="preparation evidence")
    applied = _require_dict(preparation.get("applied_answers", {}), label="applied-answer evidence")
    field_evidence = applied.get("field_evidence", [])
    coverage = _require_dict(preparation.get("answer_coverage", {}), label="answer coverage")
    verified = (
        preparation.get("submission_enabled") is False
        and preparation.get("review_ready") is True
        and evidence.get("sanitized") is True
        and evidence.get("target_bound") is True
        and evidence.get("answer_values_persisted") is False
        and applied.get("verified") is True
        and isinstance(field_evidence, list)
        and all(isinstance(item, dict) and item.get("verified") is True for item in field_evidence)
    )
    if not verified:
        _add_once(human_required, {
            "type": "preparation_evidence_unverified",
            "reason": "non_submitting_preparation_not_fully_verified",
        })
    unresolved_coverage = coverage.get("human_required", [])
    if not isinstance(unresolved_coverage, list) or unresolved_coverage:
        _add_once(human_required, {
            "type": "required_question_unanswered",
            "reason": "preparation_answer_coverage_unresolved",
        })


def _target_is_verified(
    preparation: dict,
    server_review: dict,
    expected_target: dict,
    human_required: list[dict[str, str]],
) -> bool:
    expected = {key: expected_target.get(key) for key in TARGET_KEYS}
    prepared = _binding(preparation)
    rendered = _binding(server_review)
    verified = all(isinstance(expected[key], str) and expected[key] for key in TARGET_KEYS)
    verified = verified and prepared == expected and rendered == expected
    if not verified:
        _add_once(human_required, {
            "type": "target_identity_mismatch",
            "reason": "target_id_url_company_role_or_requisition_changed",
        })
    return verified


def _field_results(
    *, profile_fields: dict, server_review: dict, human_required: list[dict[str, str]]
) -> list[dict[str, object]]:
    rendered_fields = _require_dict(server_review.get("fields", {}), label="server-rendered fields")
    results: list[dict[str, object]] = []
    for field, expected in profile_fields.items():
        if not isinstance(field, str) or not field:
            raise ReviewEvidenceError("profile field identifiers must be non-empty strings")
        verified = field in rendered_fields and rendered_fields[field] == expected
        results.append({"field": field, "verified": verified})
        if not verified:
            _add_once(human_required, {
                "type": "profile_field_mismatch",
                "field": field,
                "reason": "server_rendered_value_differs_from_profile",
            })
    return results


def _resume_result(
    *, resume_preflight: dict, server_review: dict, human_required: list[dict[str, str]]
) -> dict[str, object]:
    rendered = _require_dict(server_review.get("resume", {}), label="server-rendered resume")
    expected_hash = resume_preflight.get("sha256")
    verified = (
        resume_preflight.get("verified") is True
        and resume_preflight.get("basename") == "Resume.pdf"
        and resume_preflight.get("content_type") == "application/pdf"
        and isinstance(expected_hash, str)
        and bool(expected_hash)
        and rendered.get("basename") == "Resume.pdf"
        and rendered.get("sha256") == expected_hash
    )
    if not verified:
        _add_once(human_required, {
            "type": "resume_not_exact",
            "field": "Resume.pdf",
            "reason": "basename_content_type_or_sha256_not_verified",
        })
    return {"basename": "Resume.pdf", "verified": verified}


def _parser_repair_results(
    *,
    required_parser_repairs: list[str],
    server_review: dict,
    verified_fields: dict[str, bool],
    human_required: list[dict[str, str]],
) -> list[dict[str, object]]:
    rendered = server_review.get("parser_repairs", [])
    if not isinstance(rendered, list):
        raise ReviewEvidenceError("parser-repair evidence must be a list")
    by_field = {
        item.get("field"): item
        for item in rendered
        if isinstance(item, dict) and isinstance(item.get("field"), str)
    }
    results: list[dict[str, object]] = []
    for field in required_parser_repairs:
        evidence = by_field.get(field, {})
        verified = evidence.get("verified") is True and verified_fields.get(field) is True
        results.append({"field": field, "verified": verified})
        if not verified:
            _add_once(human_required, {
                "type": "parser_repair_unverified",
                "field": field,
                "reason": "required_repair_lacks_verified_server_readback",
            })
    return results


def _required_question_results(
    *,
    required_question_ids: list[str],
    server_review: dict,
    human_required: list[dict[str, str]],
) -> list[dict[str, object]]:
    rendered = server_review.get("questions", [])
    if not isinstance(rendered, list):
        raise ReviewEvidenceError("server-rendered questions must be a list")
    by_id = {
        item.get("id"): item
        for item in rendered
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    ordered_required = list(dict.fromkeys(required_question_ids))
    for item in rendered:
        if (
            isinstance(item, dict)
            and item.get("required") is True
            and isinstance(item.get("id"), str)
            and item["id"] not in ordered_required
        ):
            ordered_required.append(item["id"])

    results: list[dict[str, object]] = []
    for question_id in ordered_required:
        question = by_id.get(question_id, {})
        verified = question.get("answered") is True and question.get("verified") is True
        results.append({"question_id": question_id, "verified": verified})
        if not verified:
            _add_once(human_required, {
                "type": "required_question_unanswered",
                "field": question_id,
                "reason": "required_answer_lacks_verified_server_readback",
            })
    return results


def reconcile_review(
    *,
    preparation_evidence: dict,
    server_review: dict,
    expected_target: dict,
    profile_fields: dict,
    resume_preflight: dict,
    required_parser_repairs: list[str],
    required_question_ids: list[str],
) -> dict[str, Any]:
    """Return sanitized Review authority only when every exact comparison passes."""
    preparation = _require_dict(preparation_evidence, label="preparation evidence")
    rendered = _require_dict(server_review, label="server Review")
    target = _require_dict(expected_target, label="expected target")
    profile = _require_dict(profile_fields, label="profile fields")
    resume = _require_dict(resume_preflight, label="resume preflight")
    if not isinstance(required_parser_repairs, list) or not all(
        isinstance(field, str) and field for field in required_parser_repairs
    ):
        raise ReviewEvidenceError("required parser repairs must be field identifiers")
    if not isinstance(required_question_ids, list) or not all(
        isinstance(question, str) and question for question in required_question_ids
    ):
        raise ReviewEvidenceError("required questions must be question identifiers")

    human_required: list[dict[str, str]] = []
    _preparation_is_verified(preparation, human_required)
    target_verified = _target_is_verified(preparation, rendered, target, human_required)
    fields = _field_results(
        profile_fields=profile,
        server_review=rendered,
        human_required=human_required,
    )
    verified_fields = {item["field"]: item["verified"] is True for item in fields}
    resume_result = _resume_result(
        resume_preflight=resume,
        server_review=rendered,
        human_required=human_required,
    )
    parser_repairs = _parser_repair_results(
        required_parser_repairs=required_parser_repairs,
        server_review=rendered,
        verified_fields=verified_fields,
        human_required=human_required,
    )
    required_questions = _required_question_results(
        required_question_ids=required_question_ids,
        server_review=rendered,
        human_required=human_required,
    )

    result: dict[str, Any] = {
        "review_authoritative": not human_required,
        "submission_authorized": False,
        "binding": {
            **{key: target.get(key) for key in TARGET_KEYS},
            "verified": target_verified,
        },
        "fields": fields,
        "resume": resume_result,
        "parser_repairs": parser_repairs,
        "required_questions": required_questions,
        "human_required": human_required,
        "evidence": {"sanitized": True, "review_authority_only": True},
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["review_evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result
