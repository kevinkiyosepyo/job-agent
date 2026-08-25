from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_queue
import tracker
import queue_sheet_reconciliation


def test_reconcile_reports_verified_sheet_submission_drift_without_mutating_queue(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )
    queue.transition(job.id, "prepared")
    sheet_rows = [{
        "Company Name": "Example",
        "Application Status": "Submitted - Pending Response",
        "Role": "Software Engineer Intern",
        "Link to Job Req": "https://jobs.example.com/123",
    }]

    report = queue_sheet_reconciliation.reconcile(queue, sheet_rows)

    assert report["drifts"] == [{
        "job_id": job.id,
        "queue_state": "prepared",
        "sheet_status": "Submitted - Pending Response",
        "reason": "sheet_state_is_newer_verified",
    }]
    assert report["mutations"] == []
    assert queue.list_jobs()[0].state == "prepared"


def test_reconcile_reports_terminal_queue_failure_against_stale_sheet_row(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )
    leased = queue.lease_next(now="2026-08-25T00:00:00+00:00", lease_seconds=60)
    assert leased is not None
    queue.finish_lease(
        job.id,
        outcome="failed",
        now="2026-08-25T00:00:01+00:00",
        error="Unsupported ATS",
    )
    sheet_rows = [{
        "Company Name": "Example",
        "Application Status": "Discovered",
        "Role": "Software Engineer Intern",
        "Link to Job Req": "https://jobs.example.com/123?utm_source=sheet",
    }]

    report = queue_sheet_reconciliation.reconcile(queue, sheet_rows)

    assert report["drifts"] == [{
        "job_id": job.id,
        "queue_state": "failed",
        "sheet_status": "Discovered",
        "reason": "queue_state_is_newer_terminal",
    }]
    assert report["mutations"] == []
    assert queue.list_jobs()[0].state == "failed"


def test_reconcile_reports_terminal_sheet_rejection_against_nonterminal_queue_job(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )
    sheet_rows = [{
        "Company Name": "Example",
        "Application Status": "Rejected",
        "Role": "Software Engineer Intern",
        "Link to Job Req": "https://jobs.example.com/123",
    }]

    report = queue_sheet_reconciliation.reconcile(queue, sheet_rows)

    assert report["drifts"] == [{
        "job_id": job.id,
        "queue_state": "discovered",
        "sheet_status": "Rejected",
        "reason": "sheet_state_is_newer_terminal",
    }]
    assert report["mutations"] == []
    assert queue.list_jobs()[0].state == "discovered"


def test_duplicate_normalizes_tracking_parameters_and_trailing_slash():
    rows = [{
        "Company Name": "Example",
        "Role": "Software Engineer Intern",
        "Link to Job Req": "https://jobs.example.com/123/?utm_source=linkedin",
    }]
    hit = tracker.duplicate(
        rows,
        "Different Display Name",
        "Different Role",
        "https://jobs.example.com/123?source=search",
    )
    assert hit is rows[0]


def test_append_verified_reloads_tracker_and_requires_exact_row(monkeypatch):
    values = ["Example", "Discovered", "Software Engineer Intern", "", "", "https://example.com/job/1", "N/A", "test"]
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updates": {"updatedRows": 1}})
    monkeypatch.setattr(tracker, "fetch_rows_via_api", lambda: [dict(zip(tracker.HEADERS, values))])

    result = tracker.append_verified(values)

    assert result["verified"] is True
    assert result["row"]["Company Name"] == "Example"


def test_append_verified_uses_authenticated_api_when_public_csv_is_stale(monkeypatch):
    values = ["Medtronic", "Submitted - Pending Response", "Software Engineering Intern", "", "2026-08-25", "https://example.com/job/1", "N/A", "verified"]
    formatted_row = dict(zip(tracker.HEADERS, [*values[:4], "8/25/2026", *values[5:]]))
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updatedCells": 8})
    monkeypatch.setattr(tracker, "fetch_rows", lambda: [])
    monkeypatch.setattr(tracker, "fetch_rows_via_api", lambda: [formatted_row])

    result = tracker.append_verified(values)

    assert result["verified"] is True
    assert result["readback_source"] == "google_sheets_api"
    assert result["row"]["Company Name"] == "Medtronic"


def test_append_verified_fails_if_readback_does_not_contain_row(monkeypatch):
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updates": {"updatedRows": 1}})
    monkeypatch.setattr(tracker, "fetch_rows_via_api", lambda: [])

    with pytest.raises(RuntimeError, match="read-back verification"):
        tracker.append_verified(["Example", "Discovered", "Role", "", "", "https://example.com/1", "N/A", ""])


def test_run_integration_check_restores_original_rows_even_when_append_verification_fails(monkeypatch):
    original_rows = [
        {
            "Company Name": "Existing Co",
            "Application Status": "Submitted - Pending Response",
            "Role": "Software Engineer Intern",
            "Salary": "$40/hr",
            "Date Submitted": "2026-08-20",
            "Link to Job Req": "https://example.com/jobs/1",
            "Rejection Reason": "N/A",
            "Notes": "original",
        }
    ]
    restored = {}

    monkeypatch.setattr(tracker, "fetch_rows", lambda: original_rows)

    def fake_append_verified(values):
        raise RuntimeError("read-back verification failed")

    def fake_restore_rows(rows, *, blank_tail_rows):
        restored["rows"] = rows
        restored["blank_tail_rows"] = blank_tail_rows

    monkeypatch.setattr(tracker, "append_verified", fake_append_verified)
    monkeypatch.setattr(tracker, "restore_rows", fake_restore_rows)

    with pytest.raises(RuntimeError, match="read-back verification failed"):
        tracker.run_integration_check(tag="cron-test")

    assert restored == {"rows": original_rows, "blank_tail_rows": 1}


def test_main_integration_check_runs_smoke_command_and_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        tracker,
        "run_integration_check",
        lambda tag: {"status": "verified", "tag": tag, "cleanup": {"ok": True}},
    )
    monkeypatch.setattr(sys, "argv", ["tracker.py", "integration-check", "--tag", "cron-test"])

    exit_code = tracker.main()
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output == {"status": "verified", "tag": "cron-test", "cleanup": {"ok": True}}
