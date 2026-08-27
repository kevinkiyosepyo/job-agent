"""Exact-target learned confirmation and Candidate Home readers.

No reader navigates or selects a target.  The caller supplies one exact bound
page.  Tenants without a verified Candidate Home seam produce stable
human-required evidence instead of inferred submission state.
"""
from __future__ import annotations

import confirmation_reconciliation


VERIFIED_READERS: dict[tuple[str, str], str] = {
    ("greenhouse", "fixture"): "read_greenhouse_candidate_applications",
    ("workday", "fixture"): "read_workday_candidate_applications",
    ("lever", "fixture"): "read_lever_candidate_applications",
    ("oracle", "example"): "read_oracle_candidate_applications",
    ("njoyn", "cgi"): "read_njoyn_candidate_applications",
}


class LiveConfirmationReadError(ValueError):
    """The exact confirmation target could not be safely observed."""


def _snapshot(page: object, *, target_id: str, expected_url: str) -> dict:
    payload = page.read_only_snapshot()  # type: ignore[attr-defined]
    if (
        not isinstance(payload, dict)
        or payload.get("read_only") is not True
        or payload.get("target_id") != target_id
        or payload.get("url") != expected_url
        or not isinstance(payload.get("html"), str)
    ):
        raise LiveConfirmationReadError("exact confirmation target drift detected")
    return payload


def _blocked(
    *,
    platform: str,
    tenant: str,
    identity: dict[str, str],
    blocker_type: str,
    reason: str,
    confirmation: dict | None = None,
) -> dict:
    return {
        "portal_confirmed": False,
        "safe_for_post_submit": False,
        "platform": platform,
        "identity": dict(identity),
        "confirmation": (
            {
                "url": confirmation.get("confirmation_url"),
                "reference_id": confirmation.get("reference_id"),
                "submitted": confirmation.get("submitted") is True,
                "text_sha256": confirmation.get("text_sha256"),
            }
            if isinstance(confirmation, dict)
            else {"url": None, "reference_id": None, "submitted": False, "text_sha256": None}
        ),
        "portal_readback": {
            "matched_application_count": 0,
            "state": "",
            "submitted": False,
            "verified": False,
        },
        "human_required": [{"type": blocker_type, "reason": reason}],
        "evidence": {"sanitized": True, "two_source_reconciliation": False},
        "reader": {"platform": platform, "tenant": tenant, "verified": False},
    }


def read_and_reconcile(
    *,
    page: object,
    platform: str,
    tenant: str,
    target_id: str,
    expected_url: str,
    expected_identity: dict[str, str],
) -> dict:
    """Read confirmation plus one exact submitted Candidate Home record."""
    normalized_platform = platform.strip().casefold()
    if not all(
        isinstance(expected_identity.get(key), str) and expected_identity[key]
        for key in ("company", "role", "requisition")
    ):
        raise LiveConfirmationReadError("exact job identity is required")
    snapshot = _snapshot(page, target_id=target_id, expected_url=expected_url)
    try:
        confirmation = confirmation_reconciliation.extract_confirmation(
            platform=normalized_platform,
            html_text=snapshot["html"],
            page_url=expected_url,
        )
    except (ValueError, RuntimeError):
        return _blocked(
            platform=normalized_platform,
            tenant=tenant,
            identity=expected_identity,
            blocker_type="confirmation_reader_unverified",
            reason="learned_handler_did_not_verify_confirmation_surface",
        )

    method_name = VERIFIED_READERS.get((normalized_platform, tenant))
    if method_name is None:
        return _blocked(
            platform=normalized_platform,
            tenant=tenant,
            identity=expected_identity,
            blocker_type="candidate_home_reader_unverified",
            reason="tenant_lacks_verified_candidate_home_reader",
            confirmation=confirmation,
        )
    reader = getattr(page, method_name, None)
    if not callable(reader):
        reader = getattr(page, "read_candidate_applications", None)
    if not callable(reader):
        return _blocked(
            platform=normalized_platform,
            tenant=tenant,
            identity=expected_identity,
            blocker_type="candidate_home_reader_unverified",
            reason="tenant_lacks_verified_candidate_home_reader",
            confirmation=confirmation,
        )
    try:
        applications = reader()
    except (ValueError, RuntimeError):
        return _blocked(
            platform=normalized_platform,
            tenant=tenant,
            identity=expected_identity,
            blocker_type="candidate_home_read_failed",
            reason="verified_candidate_home_reader_failed_closed",
            confirmation=confirmation,
        )
    _snapshot(page, target_id=target_id, expected_url=expected_url)
    try:
        result = confirmation_reconciliation.reconcile_candidate_portal(
            confirmation=confirmation,
            expected_identity=expected_identity,
            candidate_applications=applications,
        )
    except (ValueError, RuntimeError):
        return _blocked(
            platform=normalized_platform,
            tenant=tenant,
            identity=expected_identity,
            blocker_type="candidate_home_evidence_invalid",
            reason="candidate_home_reader_returned_invalid_evidence",
            confirmation=confirmation,
        )
    result["reader"] = {
        "platform": normalized_platform,
        "tenant": tenant,
        "verified": True,
    }
    return result
