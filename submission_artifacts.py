#!/usr/bin/env python3
"""Build sanitized submission evidence artifacts with tracker/notification reconciliation."""
from __future__ import annotations

import re

import notifier
import pipeline


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


__all__ = ["build_submission_artifact", "sanitize_confirmation_excerpt"]
