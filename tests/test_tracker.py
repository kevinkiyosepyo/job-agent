from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tracker


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
    monkeypatch.setattr(tracker, "fetch_rows", lambda: [dict(zip(tracker.HEADERS, values))])

    result = tracker.append_verified(values)

    assert result["verified"] is True
    assert result["row"]["Company Name"] == "Example"


def test_append_verified_fails_if_readback_does_not_contain_row(monkeypatch):
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updates": {"updatedRows": 1}})
    monkeypatch.setattr(tracker, "fetch_rows", lambda: [])

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
