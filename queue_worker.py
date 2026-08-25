#!/usr/bin/env python3
"""Lease-aware preparation worker with durable recovery journal."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import prepare_job
from app_queue import ApplicationQueue, QueueJob
from execution_journal import ExecutionJournal


def _plan_path(*, plan_dir: Path, leased_job: QueueJob) -> Path:
    return Path(plan_dir) / f"job-{leased_job.id}-attempt-{leased_job.attempt_count}.json"


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
