"""Machine-readable, read-only operational health reporting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import app_queue
import browser_health
import queue_sheet_reconciliation
import tracker


BASE = Path.home() / "Documents/job-agent"
DEFAULT_QUEUE_PATH = BASE / "runtime/application-queue.db"
DEFAULT_OAUTH_TOKEN = Path.home() / ".hermes/google_token.json"


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


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Run read-only probes and print one operational-health JSON report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-report", required=True)
    parser.add_argument("--queue-db", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--tracker-rows", help="JSON tracker-row snapshot; live Sheets API when omitted")
    parser.add_argument("--notification-report", help="JSON read-back evidence artifact")
    parser.add_argument("--oauth-token", default=str(DEFAULT_OAUTH_TOKEN))
    parser.add_argument("--browser-base-url", default="http://127.0.0.1:18800")
    args = parser.parse_args(argv)

    source_report = _load_json(Path(args.source_report))
    if not isinstance(source_report, dict):
        raise ValueError("source report must be a JSON object")
    if args.tracker_rows:
        tracker_rows = _load_json(Path(args.tracker_rows))
        if not isinstance(tracker_rows, list):
            raise ValueError("tracker rows must be a JSON array")
    else:
        tracker_rows = tracker.fetch_rows_via_api()
    if args.notification_report:
        notification_report = _load_json(Path(args.notification_report))
        if not isinstance(notification_report, dict):
            raise ValueError("notification report must be a JSON object")
    else:
        notification_report = {"status": "unknown", "verified": False}

    queue = app_queue.ApplicationQueue(Path(args.queue_db))
    reconciliation = queue_sheet_reconciliation.reconcile(queue, tracker_rows)
    report = build_report(
        source_report=source_report,
        browser_report=browser_health.probe_cdp_health(args.browser_base_url),
        oauth_ready=Path(args.oauth_token).exists(),
        queue=queue,
        tracker_reconciliation=reconciliation,
        notification_report=notification_report,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
