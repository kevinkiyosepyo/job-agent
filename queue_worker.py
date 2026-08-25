#!/usr/bin/env python3
"""Lease-aware preparation worker with durable recovery journal."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import prepare_job
from app_queue import ApplicationQueue, QueueJob
from execution_journal import ExecutionJournal


def _plan_path(*, plan_dir: Path, leased_job: QueueJob) -> Path:
    return Path(plan_dir) / f"job-{leased_job.id}-attempt-{leased_job.attempt_count}.json"


def _closed_posting_error(html_text: str) -> str | None:
    for phrase in ("This job is no longer available.", "This position has been filled."):
        if phrase.casefold() in html_text.casefold():
            return f"Posting closed: {phrase}"
    return None


def _is_retryable_prepare_error(error: ValueError) -> bool:
    return not str(error).startswith((
        "Unsupported ATS for URL:",
        "Corrupted fixture:",
        "Posting closed:",
    ))


def resume_or_prepare_leased_job(
    *,
    queue: ApplicationQueue,
    leased_job: QueueJob,
    journal: ExecutionJournal,
    html_text: str,
    expected_resume_basename: str | None,
    now: str,
    plan_dir: Path,
) -> dict[str, Any]:
    if leased_job.state != "leased":
        raise ValueError(f"Job {leased_job.id} is not currently leased")

    plan_dir = Path(plan_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)
    latest_entry = journal.latest_step(job_id=leased_job.id, attempt_count=leased_job.attempt_count)
    recovered = False

    if latest_entry and latest_entry.get("step") == "prepared_plan_written":
        plan_path = Path(latest_entry.get("payload", {}).get("plan_path", ""))
        recovered = True
    else:
        closed_error = _closed_posting_error(html_text)
        if closed_error:
            raise ValueError(closed_error)
        plan_path = _plan_path(plan_dir=plan_dir, leased_job=leased_job)
        payload = prepare_job.prepare_saved_html(
            html_text=html_text,
            page_url=leased_job.url,
            expected_resume_basename=expected_resume_basename,
        )
        plan_path.write_text(json.dumps(payload, indent=2) + "\n")
        journal.append(
            job_id=leased_job.id,
            attempt_count=leased_job.attempt_count,
            step="prepared_plan_written",
            payload={
                "plan_path": str(plan_path),
                "platform": payload.get("platform"),
                "page_type": payload.get("page_type"),
            },
        )

    finished = queue.finish_lease(leased_job.id, outcome="prepared", now=now)
    journal.append(
        job_id=leased_job.id,
        attempt_count=leased_job.attempt_count,
        step="lease_finished",
        payload={"state": finished.state, "plan_path": str(plan_path)},
    )
    return {
        "recovered": recovered,
        "plan_path": str(plan_path),
        "queue_job": asdict(finished),
    }


def prepare_next_job(
    *,
    queue: ApplicationQueue,
    journal: ExecutionJournal,
    html_loader,
    expected_resume_basename: str | None,
    now: str,
    lease_seconds: int,
    plan_dir: Path,
) -> dict[str, Any] | None:
    leased_job = queue.lease_next(now=now, lease_seconds=lease_seconds)
    if leased_job is None:
        return None

    journal.append(
        job_id=leased_job.id,
        attempt_count=leased_job.attempt_count,
        step="lease_claimed",
        payload={
            "state": leased_job.state,
            "lease_expires_at": leased_job.lease_expires_at,
        },
    )
    return resume_or_prepare_leased_job(
        queue=queue,
        leased_job=leased_job,
        journal=journal,
        html_text=html_loader(leased_job),
        expected_resume_basename=expected_resume_basename,
        now=now,
        plan_dir=plan_dir,
    )



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-db", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--html-path", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--plan-dir", required=True)
    parser.add_argument("--expected-resume-basename")
    args = parser.parse_args(argv)

    html_path = Path(args.html_path)
    queue = ApplicationQueue(Path(args.queue_db))
    journal = ExecutionJournal(Path(args.journal))
    leased_job = queue.lease_next(now=args.now, lease_seconds=args.lease_seconds)
    if leased_job is None:
        print(json.dumps({"status": "no_job_available"}))
        return 0

    journal.append(
        job_id=leased_job.id,
        attempt_count=leased_job.attempt_count,
        step="lease_claimed",
        payload={
            "state": leased_job.state,
            "lease_expires_at": leased_job.lease_expires_at,
        },
    )

    try:
        result = resume_or_prepare_leased_job(
            queue=queue,
            leased_job=leased_job,
            journal=journal,
            html_text=html_path.read_text(),
            expected_resume_basename=args.expected_resume_basename,
            now=args.now,
            plan_dir=Path(args.plan_dir),
        )
    except ValueError as exc:
        retryable = _is_retryable_prepare_error(exc)
        journal.append(
            job_id=leased_job.id,
            attempt_count=leased_job.attempt_count,
            step="prepare_blocked",
            payload={"error": str(exc), "retryable": retryable},
        )
        finished = queue.finish_lease(
            leased_job.id,
            outcome="retry" if retryable else "failed",
            now=args.now,
            retry_seconds=0,
            error=str(exc),
        )
        journal.append(
            job_id=leased_job.id,
            attempt_count=leased_job.attempt_count,
            step="lease_finished",
            payload={"state": finished.state, "error": str(exc)},
        )
        print(json.dumps({
            "status": "posting_closed" if str(exc).startswith("Posting closed:") else "prepare_blocked",
            "error": str(exc),
            "job_id": leased_job.id,
            "retryable": retryable,
            "submission_enabled": False,
        }))
        return 2

    print(json.dumps({"status": "prepared", "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
