"""Read-only reconciliation between local queue state and tracker rows."""
from __future__ import annotations

from typing import Iterable

import app_queue
import tracker

_VERIFIED_SHEET_STATUSES = {"Submitted - Pending Response"}


def reconcile(
    queue: app_queue.ApplicationQueue,
    sheet_rows: Iterable[dict[str, str]],
) -> dict:
    """Report state drift only; reconciliation never mutates either system."""
    statuses_by_url = {
        tracker.normalize_job_url(row.get("Link to Job Req") or ""): row.get("Application Status") or ""
        for row in sheet_rows
        if (row.get("Link to Job Req") or "").strip()
    }
    drifts = []
    for job in queue.list_jobs():
        sheet_status = statuses_by_url.get(tracker.normalize_job_url(job.url))
        if sheet_status in _VERIFIED_SHEET_STATUSES and job.state != "applied":
            drifts.append(
                {
                    "job_id": job.id,
                    "queue_state": job.state,
                    "sheet_status": sheet_status,
                    "reason": "sheet_state_is_newer_verified",
                }
            )
    return {"drifts": drifts, "mutations": []}
