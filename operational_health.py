"""Machine-readable, read-only operational health reporting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

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
    oauth_ready: bool = False,
    queue: app_queue.ApplicationQueue,
    tracker_reconciliation: dict[str, Any] | None = None,
    notification_report: dict[str, Any],
    oauth_required: bool = False,
) -> dict[str, Any]:
    """Summarize operational evidence without changing any external state."""
    jobs = queue.list_jobs()
    leased = [job for job in jobs if job.state == "leased"]
    expired = [job for job in leased if job.lease_expires_at is None]
    tracker_required = tracker_reconciliation is not None
    oauth_required = oauth_required or tracker_required
    drift_count = len((tracker_reconciliation or {}).get("drifts", []))
    tracker_available = (tracker_reconciliation or {}).get("status") not in {
        "failed", "error", "unavailable", "unknown"}
    readiness = {
        "sources": source_report.get("source_health_status") == "healthy",
        "browser": (browser_report.get("status") == "ready"
                    and browser_report.get("verified") is True),
        "notifications": (notification_report.get("status") == "delivered"
                          and notification_report.get("verified") is True),
        "oauth": oauth_ready is True,
        "tracker": tracker_required and tracker_available and not drift_count,
    }
    required = ["sources", "browser", "notifications"]
    if oauth_required:
        required.append("oauth")
    if tracker_required:
        required.append("tracker")
    blocked = [name for name in required if not readiness[name]]
    return {
        "status": "degraded" if blocked else "ready",
        "dependencies": {"required": required,
                         "optional": [name for name in readiness if name not in required],
                         "blocked_by": blocked},
        "sources": {"status": source_report.get("source_health_status", "unknown")},
        "browser": browser_report,
        "oauth": {"status": "ready" if oauth_ready else "unavailable"},
        "queue": {"leased_count": len(leased), "expired_lease_count": len(expired)},
        "tracker": {"drift_count": drift_count, "status": (
            "not_requested" if not tracker_required else "unavailable" if not tracker_available else
            "drift_detected" if drift_count else "in_sync")},
        "notifications": notification_report,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None, *,
         browser_caller: Callable[[], dict] | None = None,
         oauth_probe: Callable[[], bool] | None = None) -> int:
    """Run read-only probes and print one operational-health JSON report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-report", required=True)
    parser.add_argument("--queue-db", default=str(DEFAULT_QUEUE_PATH))
    parser.add_argument("--tracker-rows", help="Explicit opt-in JSON tracker-row snapshot")
    parser.add_argument("--check-tracker", action="store_true", help="Explicit opt-in live Sheets read")
    parser.add_argument("--require-oauth", action="store_true")
    parser.add_argument("--notification-report", help="JSON read-back evidence artifact")
    parser.add_argument("--oauth-token", default=str(DEFAULT_OAUTH_TOKEN))
    parser.add_argument("--browser-base-url", default="http://127.0.0.1:18800")
    args = parser.parse_args(argv)

    source_report = _load_json(Path(args.source_report))
    if not isinstance(source_report, dict):
        raise ValueError("source report must be a JSON object")
    tracker_failure = None
    if args.tracker_rows:
        tracker_rows = _load_json(Path(args.tracker_rows))
        if not isinstance(tracker_rows, list):
            raise ValueError("tracker rows must be a JSON array")
    elif args.check_tracker:
        try:
            tracker_rows = tracker.fetch_rows_via_api()
        except Exception:
            tracker_rows = None
            tracker_failure = {"status": "unavailable", "drifts": []}
    else:
        tracker_rows = None
    if args.notification_report:
        notification_report = _load_json(Path(args.notification_report))
        if not isinstance(notification_report, dict):
            raise ValueError("notification report must be a JSON object")
    else:
        notification_report = {"status": "unknown", "verified": False}

    queue = app_queue.ApplicationQueue(Path(args.queue_db))
    reconciliation = (queue_sheet_reconciliation.reconcile(queue, tracker_rows)
                      if tracker_rows is not None else None)
    if tracker_failure is not None:
        reconciliation = tracker_failure
    oauth_ready = False
    if oauth_probe is not None and (args.require_oauth or reconciliation is not None):
        try:
            oauth_ready = oauth_probe() is True
        except Exception:
            oauth_ready = False
    report = build_report(
        source_report=source_report,
        browser_report=browser_health.probe_transport_health(caller=browser_caller),
        oauth_ready=oauth_ready,
        oauth_required=args.require_oauth,
        queue=queue,
        tracker_reconciliation=reconciliation,
        notification_report=notification_report,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
