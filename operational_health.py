"""Machine-readable, read-only operational health reporting."""
from __future__ import annotations

from typing import Any

import app_queue


def build_report(
    *,
    source_report: dict[str, Any],
    browser_report: dict[str, Any],
    oauth_ready: bool,
    queue: app_queue.ApplicationQueue,
    tracker_reconciliation: dict[str, Any],
    notification_report: dict[str, Any],
) -> dict[str, Any]:
    """Summarize operational evidence without changing any external state."""
    jobs = queue.list_jobs()
    leased = [job for job in jobs if job.state == "leased"]
    expired = [job for job in leased if job.lease_expires_at is None]
    drift_count = len(tracker_reconciliation.get("drifts", []))
    return {
        "status": "degraded" if drift_count else "ready",
        "sources": {"status": source_report.get("source_health_status", "unknown")},
        "browser": browser_report,
        "oauth": {"status": "ready" if oauth_ready else "unavailable"},
        "queue": {"leased_count": len(leased), "expired_lease_count": len(expired)},
        "tracker": {"drift_count": drift_count, "status": "drift_detected" if drift_count else "in_sync"},
        "notifications": notification_report,
    }
