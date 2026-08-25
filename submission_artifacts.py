#!/usr/bin/env python3
"""Build sanitized submission evidence artifacts with tracker/notification reconciliation."""
from __future__ import annotations

import re
from copy import deepcopy

import notifier
import pipeline
import tracker


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d[\d .()-]{6,}\d)\b")


def sanitize_confirmation_excerpt(text: str) -> str:
    excerpt = pipeline.normalize_confirmation_text(text)
    excerpt = _EMAIL_RE.sub("[REDACTED_EMAIL]", excerpt)
    excerpt = _PHONE_RE.sub("[REDACTED_PHONE]", excerpt)
    return excerpt


def build_submission_artifact(job: dict, *, confirmation_url: str, confirmation_text: str) -> dict:
    tracker_values = pipeline.submission_row(
        job,
        confirmation_url=confirmation_url,
        confirmation_text=confirmation_text,
    )
    notification_message = notifier.build_message(
        "applied",
        company=job.get("company", ""),
        role=job.get("role", ""),
        url=job.get("url", ""),
    )
    return {
        "tracker": {
            "values": tracker_values,
        },
        "notification": {
            "kind": "applied",
            "message": notification_message,
        },
        "evidence": {
            "confirmation_url": confirmation_url.strip(),
            "confirmation_excerpt": sanitize_confirmation_excerpt(confirmation_text),
        },
        "reconciliation": {
            "tracker_status": tracker_values[1],
            "notification_kind": "applied",
            "consistent": tracker_values[1] == "Submitted - Pending Response",
        },
    }


def _expected_tracker_row(values: list[str]) -> dict[str, str]:
    return dict(zip(tracker.HEADERS, values))


def reconcile_submission_delivery(
    artifact: dict,
    *,
    tracker_result: dict,
    notification_result: dict,
) -> dict:
    reconciled = deepcopy(artifact)
    tracker_row = tracker_result.get("row") or {}
    expected_tracker_row = _expected_tracker_row(reconciled["tracker"]["values"])
    tracker_verified = bool(tracker_result.get("verified"))
    tracker_matches_expected = tracker_verified and all(
        (tracker_row.get(header) or "") == (expected_tracker_row.get(header) or "")
        for header in tracker.HEADERS
    )

    delivered_message = ((notification_result.get("read_back") or {}).get("message") or "").strip()
    notification_delivered = bool(notification_result.get("delivered"))
    expected_message = reconciled["notification"]["message"]
    notification_matches_expected = notification_delivered and delivered_message == expected_message

    reconciled["tracker"].update({
        "verified": tracker_verified,
        "row": tracker_row,
    })
    reconciled["notification"].update({
        "delivered": notification_delivered,
        "target": notification_result.get("target", ""),
        "read_back": delivered_message,
    })
    reconciled["reconciliation"] = {
        "tracker_status": expected_tracker_row["Application Status"],
        "notification_kind": reconciled["notification"]["kind"],
        "tracker_verified": tracker_verified,
        "notification_delivered": notification_delivered,
        "tracker_matches_expected": tracker_matches_expected,
        "notification_matches_expected": notification_matches_expected,
        "consistent": tracker_matches_expected and notification_matches_expected,
    }
    return reconciled


__all__ = [
    "build_submission_artifact",
    "reconcile_submission_delivery",
    "sanitize_confirmation_excerpt",
]
