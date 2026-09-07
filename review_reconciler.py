"""Authoritative, sanitized reconciliation of an ATS Review surface.

The reconciler is deliberately pure and non-submitting. It compares explicitly
sourced server-saved or bound-client state with independently supplied canonical
profile fields, resume bytes, question mappings, repair and target facts. The
caller must build profile_fields from the accepted profile, never from answer
actions (see canonical_answers.canonical_review_fields). Private inputs are
committed cryptographically but never returned; unresolved facts fail closed.
"""
from __future__ import annotations

import hashlib
import json
import re
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
    if not profile_fields:
        _add_once(human_required, {"type": "unknown_profile_fact", "reason": "canonical_review_fields_missing"})
    for field in sorted(rendered_fields.keys() - profile_fields.keys()):
        _add_once(human_required, {"type": "unknown_profile_fact", "field": field,
                                  "reason": "rendered_field_has_no_canonical_source"})
    for field, expected in sorted(profile_fields.items()):
        if not isinstance(field, str) or not field:
            raise ReviewEvidenceError("profile field identifiers must be non-empty strings")
        known = isinstance(expected, (str, bool, int, float)) and expected is not None and expected != ''
        verified = known and field in rendered_fields and rendered_fields[field] == expected
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
    expected_basename = resume_preflight.get("basename")
    rendered_hash = rendered.get("sha256")
    verified = (
        resume_preflight.get("verified") is True
        and isinstance(expected_basename, str)
        and bool(expected_basename)
        and expected_basename.casefold().endswith(".pdf")
        and resume_preflight.get("content_type") == "application/pdf"
        and isinstance(expected_hash, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected_hash) is not None
        and rendered.get("basename") == expected_basename
        and rendered_hash == expected_hash
    )
    if not verified:
        _add_once(human_required, {
            "type": "resume_not_exact",
            "field": expected_basename if isinstance(expected_basename, str) else "resume",
            "reason": "basename_content_type_or_sha256_not_verified",
        })
    return {
        "basename": expected_basename if isinstance(expected_basename, str) else "",
        "verified": verified,
    }


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
    verified_fields: dict[str, bool],
    question_fields: dict,
    human_required: list[dict[str, str]],
) -> list[dict[str, object]]:
    rendered = server_review.get("questions", [])
    if not isinstance(rendered, list):
        raise ReviewEvidenceError("server-rendered questions must be a list")
    ids = [item.get("id") for item in rendered if isinstance(item, dict)]
    if (len(ids) != len(rendered) or any(not isinstance(key, str) or not key for key in ids)
        or len(set(key for key in ids if isinstance(key, str))) != len(ids)):
        _add_once(human_required, {"type": "required_question_unanswered",
                                  "reason": "ambiguous_or_missing_question_identity"})
    by_id = {
        item.get("id"): item
        for item in rendered
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    ordered_required = list(dict.fromkeys(required_question_ids))
    for item in rendered:
        if (
            isinstance(item, dict)
            and (item.get("required") is True or item.get("answered") is True)
            and isinstance(item.get("id"), str)
            and item["id"] not in ordered_required
        ):
            ordered_required.append(item["id"])

    results: list[dict[str, object]] = []
    for question_id in ordered_required:
        question = by_id.get(question_id, {})
        field = question_fields.get(question_id, question_id)
        verified = (question.get("answered") is True and question.get("verified") is True
                    and isinstance(field, str) and verified_fields.get(field) is True
                    and ('answer' not in question or question['answer'] == server_review.get('fields', {}).get(field)))
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
    question_fields: dict | None = None,
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
    source = rendered.get("source")
    from schonfeld_form import URL as SCHONFELD_URL
    if (
        source not in ("live_client_bound_form", "server_saved_review")
        or (source == "server_saved_review" and rendered.get("server_saved") is not True)
        or (target.get("page_url") == SCHONFELD_URL and source != "live_client_bound_form")
    ):
        human_required.append({"type": "unknown_review_source", "reason": "unsupported_provenance"})
    if source == "live_client_bound_form":
        from datetime import datetime, timezone
        try:
            observed = datetime.fromisoformat(rendered.get("observed_at", ""))
            fresh = observed.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 120
        except (ValueError, TypeError):
            fresh = False
        completeness = _require_dict(rendered.get("completeness"), label="client completeness")
        bindings = _require_dict(rendered.get("bindings"), label="client bindings")
        attached = _require_dict(rendered.get("resume"), label="client attachment")
        rendered_fields = _require_dict(rendered.get("fields"), label="client fields")
        required = completeness.get("required_selectors")
        valid = (
            rendered.get("server_saved") is False and fresh
            and set(rendered_fields) == set(profile)
            and completeness.get("verified") is True
            and all(completeness.get(key) == [] for key in ("unknown_controls", "invalid_controls", "gates"))
            and isinstance(required, list) and bool(required) and set(required) <= set(profile)
            and all(isinstance(bindings.get(field), dict) and bindings[field].get("count") == 1
                    and all(bindings[field].get(key) is True for key in ("bound", "valid", "visible", "enabled"))
                    for field in profile)
            and attached.get("attachment_present") is True
            and attached.get("source") == "live_browser_file"
            and attached.get("content_type") == "application/pdf"
            and isinstance(attached.get("sha256"), str) and len(attached["sha256"]) == 64
            and attached.get("sha256") == resume.get("sha256")
        )
        if not valid:
            human_required.append({"type": "client_form_unverified", "reason": "fresh_complete_bound_form_and_exact_attachment_required"})
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
        verified_fields=verified_fields,
        question_fields=_require_dict(question_fields or {}, label="canonical question fields"),
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
    if rendered.get("source") == "live_client_bound_form":
        result.update(source="live_client_bound_form", server_saved=False)
        state = {key: value for key, value in rendered.items() if key != "observed_at"}
        result["evidence"]["client_state_sha256"] = hashlib.sha256(
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        result["evidence"]["input_binding"] = preparation.get("evidence", {}).get("input_binding", {})
    # Commit private content, not just the public comparison flags. Timestamps
    # measure freshness but are not form state (a fresh re-read must be stable).
    state = {key: value for key, value in rendered.items() if key != "observed_at"}
    commitment = {"version": 1, "observed": state, "canonical_fields": profile,
                  "resume_preflight": resume, "question_fields": question_fields or {},
                  "input_binding": preparation.get("evidence", {}).get("input_binding", {})}
    result["evidence"]["content_sha256"] = hashlib.sha256(
        json.dumps(commitment, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result["review_evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result
