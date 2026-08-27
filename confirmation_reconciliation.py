"""Learned-ATS confirmation extraction and candidate-portal reconciliation."""
from __future__ import annotations

import hashlib
import re
from typing import Callable

import greenhouse_handler
import lever_handler
import njoyn_handler
import oracle_handler
import workday_handler


InspectHandler = Callable[..., dict]
HANDLERS: dict[str, InspectHandler] = {
    "greenhouse": greenhouse_handler.inspect_html,
    "workday": workday_handler.inspect_html,
    "lever": lever_handler.inspect_html,
    "oracle": oracle_handler.inspect_html,
    "njoyn": njoyn_handler.inspect_html,
}


class ConfirmationEvidenceError(ValueError):
    """A learned ATS handler did not prove a confirmation surface."""


def extract_confirmation(*, platform: str, html_text: str, page_url: str) -> dict:
    """Extract sanitized explicit-submission evidence through one learned handler."""
    normalized_platform = platform.strip().casefold()
    handler = HANDLERS.get(normalized_platform)
    if handler is None:
        raise ConfirmationEvidenceError(f"unsupported learned ATS: {platform}")
    if not isinstance(html_text, str) or not html_text or not isinstance(page_url, str) or not page_url:
        raise ConfirmationEvidenceError("confirmation HTML and URL are required")
    payload = handler(html_text, page_url=page_url)
    confirmation_text = payload.get("confirmation_text")
    if payload.get("page_type") != "confirmation" or not isinstance(confirmation_text, str) or not confirmation_text:
        raise ConfirmationEvidenceError("learned ATS handler did not verify a confirmation page")
    reference = payload.get("confirmation_reference_id")
    return {
        "platform": normalized_platform,
        "confirmation_url": page_url,
        "submitted": True,
        "explicit_state": "submitted",
        "reference_id": reference if isinstance(reference, str) and reference else None,
        "text_sha256": hashlib.sha256(confirmation_text.encode("utf-8")).hexdigest(),
        "sanitized": True,
    }


def _contains_exact(text: str, value: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(value) + r"(?![A-Za-z0-9_-])", text) is not None


def _is_exact_identity(record: dict, *, platform: str, identity: dict[str, str]) -> bool:
    return (
        str(record.get("platform", "")).casefold() == platform
        and all(record.get(key) == identity[key] for key in ("company", "role", "requisition"))
    )


def _is_explicit_submitted(record: dict) -> bool:
    return str(record.get("state", "")).casefold() == "submitted" and record.get("submitted") is True


def _block(human_required: list[dict[str, str]], blocker_type: str, reason: str) -> None:
    item = {"type": blocker_type, "reason": reason}
    if item not in human_required:
        human_required.append(item)


def reconcile_candidate_portal(
    *,
    confirmation: dict,
    expected_identity: dict[str, str],
    candidate_applications: list[dict],
) -> dict:
    """Require confirmation plus one exact explicitly-submitted portal record."""
    if not isinstance(confirmation, dict) or confirmation.get("sanitized") is not True:
        raise ConfirmationEvidenceError("sanitized confirmation evidence is required")
    platform = confirmation.get("platform")
    if not isinstance(platform, str) or platform not in HANDLERS:
        raise ConfirmationEvidenceError("learned ATS confirmation platform is required")
    if not isinstance(expected_identity, dict) or not all(
        isinstance(expected_identity.get(key), str) and expected_identity[key]
        for key in ("company", "role", "requisition")
    ):
        raise ConfirmationEvidenceError("exact company, role, and requisition are required")
    if not isinstance(candidate_applications, list) or not all(
        isinstance(item, dict) for item in candidate_applications
    ):
        raise ConfirmationEvidenceError("candidate application read-back must be a list")

    human_required: list[dict[str, str]] = []
    if confirmation.get("submitted") is not True or confirmation.get("explicit_state") != "submitted":
        _block(
            human_required,
            "confirmation_state_not_submitted",
            "confirmation_did_not_report_explicit_submitted_state",
        )
    confirmation_url = confirmation.get("confirmation_url")
    reference_id = confirmation.get("reference_id")
    requisition = expected_identity["requisition"]
    requisition_verified = (
        isinstance(confirmation_url, str)
        and _contains_exact(confirmation_url, requisition)
    ) or reference_id == requisition
    if not requisition_verified:
        _block(
            human_required,
            "confirmation_requisition_mismatch",
            "confirmation_url_or_reference_did_not_match_requisition",
        )

    platform_records = [
        item
        for item in candidate_applications
        if str(item.get("platform", "")).casefold() == platform
    ]
    identity_matches = [
        item
        for item in platform_records
        if _is_exact_identity(item, platform=platform, identity=expected_identity)
    ]
    submitted_records = [item for item in platform_records if _is_explicit_submitted(item)]
    exact_submitted = [item for item in identity_matches if _is_explicit_submitted(item)]

    if not identity_matches or (submitted_records and not exact_submitted):
        _block(
            human_required,
            "portal_identity_mismatch",
            "submitted_portal_record_did_not_match_company_role_and_requisition",
        )
    if identity_matches and not exact_submitted:
        _block(
            human_required,
            "portal_state_not_submitted",
            "exact_portal_record_lacked_explicit_submitted_state",
        )
    if len(exact_submitted) > 1:
        _block(
            human_required,
            "portal_record_ambiguous",
            "multiple_exact_submitted_portal_records_found",
        )

    portal_verified = len(exact_submitted) == 1
    result = {
        "portal_confirmed": not human_required and portal_verified,
        "safe_for_post_submit": not human_required and portal_verified,
        "platform": platform,
        "identity": {
            key: expected_identity[key] for key in ("company", "role", "requisition")
        },
        "confirmation": {
            "url": confirmation_url,
            "reference_id": reference_id,
            "submitted": confirmation.get("submitted") is True,
            "text_sha256": confirmation.get("text_sha256"),
        },
        "portal_readback": {
            "matched_application_count": len(exact_submitted),
            "state": "submitted" if portal_verified else "",
            "submitted": portal_verified,
            "verified": portal_verified,
        },
        "human_required": human_required,
        "evidence": {"sanitized": True, "two_source_reconciliation": True},
    }
    return result
