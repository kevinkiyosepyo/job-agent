from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_queue
import operational_health


def test_build_report_summarizes_all_required_operational_surfaces(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://job-boards.greenhouse.io/example/jobs/123",
        ats_platform="Greenhouse",
    )
    leased = queue.lease_next(now="2026-08-25T08:00:00+00:00", lease_seconds=300)
    assert leased is not None

    report = operational_health.build_report(
        source_report={"source_health_status": "healthy"},
        browser_report={"status": "ready", "recoverable": False},
        oauth_ready=True,
        queue=queue,
        tracker_reconciliation={"drifts": [{"job_id": 99}], "mutations": []},
        notification_report={"status": "delivered", "verified": True},
    )

    assert report == {
        "status": "degraded",
        "sources": {"status": "healthy"},
        "browser": {"status": "ready", "recoverable": False},
        "oauth": {"status": "ready"},
        "queue": {"leased_count": 1, "expired_lease_count": 0},
        "tracker": {"drift_count": 1, "status": "drift_detected"},
        "notifications": {"status": "delivered", "verified": True},
    }
