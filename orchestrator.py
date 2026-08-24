#!/usr/bin/env python3
"""Dry-run scan → route → queue → report orchestration CLI."""
from __future__ import annotations

import argparse
import fcntl
import json
from dataclasses import asdict
from pathlib import Path

from app_queue import ApplicationQueue
from audit_log import AuditLogger
import pipeline
import scanner


BASE = Path.home() / "Documents/job-agent"
VALID_SOURCE_HEALTH_STATUSES = {"healthy", "partial_error", "stale_or_unknown"}


class RunLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = None

    def __enter__(self) -> "RunLock":
        self._handle = self.path.open("a+")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._handle.close()
            self._handle = None
            raise SystemExit("Another job-agent run is already active")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._handle is not None
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


def build_scan(candidates: list[dict], profile: dict) -> dict:
    jobs = scanner.unique_jobs(candidates)
    results = [scanner.classify(job, profile) for job in jobs]
    new = [job for job in results if job["relevant"] and not job["duplicate"]]
    manual = [job for job in new if job["manual_only"]]
    queue = [job for job in new if not job["manual_only"]]
    return {
        "scanned": len(results),
        "new": len(new),
        "manual_only": manual,
        "auto_apply_queue": queue,
        "all_results": results,
    }


def enqueue_plan_jobs(queue_db: Path, routed: dict[str, list[dict]]) -> list[dict]:
    app_queue = ApplicationQueue(queue_db)
    for key in ("greenhouse", "workday"):
        for job in routed.get(key, []):
            app_queue.enqueue(
                company=job["company"],
                role=job["role"],
                url=job["url"],
                ats_platform=job["ats_platform"],
            )
    return [asdict(job) for job in app_queue.list_jobs()]


def _has_non_ok_source_runs(report: dict) -> bool:
    source_runs = report.get("source_runs")
    if not isinstance(source_runs, list):
        return False
    for run in source_runs:
        if not isinstance(run, dict):
            continue
        if run.get("status") != "ok":
            return True
        if run.get("stale_result") or run.get("freshness_unknown"):
            return True
    return False


def _expected_freshness_summary(report: dict) -> dict[str, int] | None:
    source_runs = report.get("source_runs")
    if not isinstance(source_runs, list):
        return None
    stale_runs = sum(1 for run in source_runs if isinstance(run, dict) and run.get("stale_result"))
    freshness_unknown_runs = sum(1 for run in source_runs if isinstance(run, dict) and run.get("freshness_unknown"))
    error_runs = sum(1 for run in source_runs if isinstance(run, dict) and run.get("status") == "error")
    return {
        "total_runs": len(source_runs),
        "healthy_runs": len(source_runs) - stale_runs - freshness_unknown_runs - error_runs,
        "stale_runs": stale_runs,
        "freshness_unknown_runs": freshness_unknown_runs,
        "error_runs": error_runs,
    }


def _has_inconsistent_freshness_summary(report: dict) -> bool:
    freshness_summary = report.get("freshness_summary")
    if not isinstance(freshness_summary, dict):
        return False
    expected = _expected_freshness_summary(report)
    if expected is None:
        return False
    return freshness_summary != expected


def _expected_freshness_buckets(report: dict) -> dict[str, list[dict[str, str]]] | None:
    source_runs = report.get("source_runs")
    if not isinstance(source_runs, list):
        return None
    buckets = {
        "healthy": [],
        "stale": [],
        "freshness_unknown": [],
        "error": [],
    }
    for run in source_runs:
        if not isinstance(run, dict):
            continue
        entry = {"source": run.get("source"), "token": run.get("token")}
        if run.get("status") == "error":
            buckets["error"].append(entry)
        elif run.get("freshness_unknown"):
            buckets["freshness_unknown"].append(entry)
        elif run.get("stale_result"):
            buckets["stale"].append(entry)
        else:
            buckets["healthy"].append(entry)
    return buckets


def _has_inconsistent_freshness_buckets(report: dict) -> bool:
    freshness_buckets = report.get("freshness_buckets")
    if not isinstance(freshness_buckets, dict):
        return False
    expected = _expected_freshness_buckets(report)
    if expected is None:
        return False
    return freshness_buckets != expected


def load_source_report(source_report_path: Path | None) -> dict | None:
    if source_report_path is None:
        return None
    try:
        report = json.loads(source_report_path.read_text())
    except OSError as exc:
        raise SystemExit("Invalid source report: unreadable") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit("Invalid source report: invalid_json") from exc
    if not isinstance(report, dict):
        raise SystemExit("Invalid source report: invalid_schema")
    if "source_health_status" not in report:
        raise SystemExit("Invalid source report: missing_source_health_status")
    status = report["source_health_status"]
    if not isinstance(status, str) or status not in VALID_SOURCE_HEALTH_STATUSES:
        raise SystemExit("Invalid source report: invalid_source_health_status")
    if status == "healthy" and (
        report.get("failures")
        or _has_non_ok_source_runs(report)
        or _has_inconsistent_freshness_summary(report)
        or _has_inconsistent_freshness_buckets(report)
    ):
        raise SystemExit("Invalid source report: inconsistent_source_health")
    if status != "healthy":
        raise SystemExit(f"Source health check failed: {status}")
    return report


def run(
    candidates_path: Path,
    profile_path: Path,
    output_path: Path,
    queue_db: Path,
    audit_log_path: Path,
    source_report_path: Path | None = None,
) -> dict:
    profile = json.loads(profile_path.read_text())
    errors = pipeline.validate_profile(profile)
    if errors:
        raise SystemExit("Invalid profile: " + ", ".join(errors))

    source_report = load_source_report(source_report_path)

    candidates = json.loads(candidates_path.read_text())
    scan = build_scan(candidates, profile)
    plan = {
        "mode": "plan_only",
        "submission_enabled": False,
        "routes": pipeline.route_candidates(scan),
    }
    plan["counts"] = {key: len(value) for key, value in plan["routes"].items()}

    queued_jobs = enqueue_plan_jobs(queue_db, plan["routes"])
    payload = {
        "mode": "dry_run",
        "scan": scan,
        "plan": plan,
        "queue": {"count": len(queued_jobs), "jobs": queued_jobs},
    }
    if source_report is not None:
        payload["source_report"] = source_report
    output_path.write_text(json.dumps(payload, indent=2) + "\n")

    logger = AuditLogger(audit_log_path)
    logger.log(
        "dry_run_completed",
        {
            "profile": profile,
            "counts": payload["plan"]["counts"],
            "queue_count": payload["queue"]["count"],
            "output": str(output_path),
        },
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", help="Verified candidates JSON array")
    parser.add_argument("--profile", default=str(BASE / "profile.json"))
    parser.add_argument("--output", default=str(BASE / "orchestrator-report.json"))
    parser.add_argument("--queue-db", default=str(BASE / "runtime/app_queue.sqlite3"))
    parser.add_argument("--audit-log", default=str(BASE / "runtime/audit.jsonl"))
    parser.add_argument("--lock-path", default=str(BASE / "runtime/orchestrator.lock"))
    parser.add_argument("--source-report", help="Optional sources.py report JSON path")
    args = parser.parse_args(argv)

    with RunLock(Path(args.lock_path)):
        payload = run(
            Path(args.candidates),
            Path(args.profile),
            Path(args.output),
            Path(args.queue_db),
            Path(args.audit_log),
            Path(args.source_report) if args.source_report else None,
        )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
