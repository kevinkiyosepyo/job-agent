from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_queue
import execution_journal
import prepare_job
import queue_worker


def test_resume_or_prepare_leased_job_recovers_after_plan_was_already_written(tmp_path, monkeypatch):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://job-boards.greenhouse.io/example/jobs/123",
        ats_platform="Greenhouse",
    )
    leased = queue.lease_next(now="2026-08-25T07:35:00+00:00", lease_seconds=300)
    assert leased is not None

    journal = execution_journal.ExecutionJournal(tmp_path / "journal.jsonl")
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir()
    plan_path = plan_dir / "job-1-attempt-1.json"
    existing_plan = prepare_job.prepare_saved_html(
        html_text=(ROOT / "fixtures" / "greenhouse.html").read_text(),
        page_url=job.url,
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
    )
    plan_path.write_text(json.dumps(existing_plan))
    journal.append(
        job_id=leased.id,
        attempt_count=leased.attempt_count,
        step="prepared_plan_written",
        payload={"plan_path": str(plan_path)},
    )

    def fail_prepare(**kwargs):
        raise AssertionError("prepare_saved_html should not run during recovery")

    monkeypatch.setattr(queue_worker.prepare_job, "prepare_saved_html", fail_prepare)

    result = queue_worker.resume_or_prepare_leased_job(
        queue=queue,
        leased_job=leased,
        journal=journal,
        html_text="<html>should not be reparsed during recovery</html>",
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
        now="2026-08-25T07:36:00+00:00",
        plan_dir=plan_dir,
    )

    assert result["recovered"] is True
    assert result["plan_path"] == str(plan_path)
    assert result["queue_job"]["state"] == "prepared"
    assert json.loads(plan_path.read_text()) == existing_plan

    steps = [entry["step"] for entry in journal.read_all()]
    assert steps == ["prepared_plan_written", "lease_finished"]
