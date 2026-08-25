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


def test_main_runs_read_only_probes_and_emits_machine_readable_report(tmp_path, monkeypatch, capsys):
    queue_path = tmp_path / "queue.db"
    queue = app_queue.ApplicationQueue(queue_path)
    queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://job-boards.greenhouse.io/example/jobs/123",
        ats_platform="Greenhouse",
    )
    source_report = tmp_path / "sources-report.json"
    source_report.write_text('{"source_health_status": "healthy"}', encoding="utf-8")
    tracker_rows = tmp_path / "tracker-rows.json"
    tracker_rows.write_text('[]', encoding="utf-8")
    notification_report = tmp_path / "notification-report.json"
    notification_report.write_text('{"status": "delivered", "verified": true}', encoding="utf-8")
    oauth_token = tmp_path / "oauth.json"
    oauth_token.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        operational_health.browser_health,
        "probe_cdp_health",
        lambda url: {"status": "ready", "recoverable": False, "base_url": url},
    )

    assert operational_health.main([
        "--source-report", str(source_report),
        "--queue-db", str(queue_path),
        "--tracker-rows", str(tracker_rows),
        "--notification-report", str(notification_report),
        "--oauth-token", str(oauth_token),
        "--browser-base-url", "http://browser.test:18800",
    ]) == 0

    report = __import__("json").loads(capsys.readouterr().out)
    assert report["status"] == "ready"
    assert report["sources"] == {"status": "healthy"}
    assert report["browser"] == {"status": "ready", "recoverable": False, "base_url": "http://browser.test:18800"}
    assert report["oauth"] == {"status": "ready"}
    assert report["queue"] == {"leased_count": 0, "expired_lease_count": 0}
    assert report["tracker"] == {"drift_count": 0, "status": "in_sync"}
    assert report["notifications"] == {"status": "delivered", "verified": True}
