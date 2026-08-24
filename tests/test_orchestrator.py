from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import orchestrator


def test_dry_run_orchestrates_scan_route_queue_and_audit(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_text("fixture resume")
    profile_path.write_text(
        json.dumps(
            {
                "name": {"full": "Test User"},
                "contact": {"email": "test@example.com", "phone": "555-1111"},
                "resume": {"primary": str(resume_path)},
                "preferences": {"target_roles": ["Software Engineer Intern"]},
            }
        )
    )

    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "company": "Example",
                    "role": "Software Engineer Intern",
                    "url": "https://job-boards.greenhouse.io/example/jobs/1?utm_source=linkedin",
                    "salary": "$40/hr",
                },
                {
                    "company": "Google",
                    "role": "Software Engineer Intern",
                    "url": "https://careers.google.com/jobs/results/2",
                },
            ]
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    output_path = tmp_path / "orchestrator-report.json"
    exit_code = orchestrator.main(
        [
            str(candidates_path),
            "--profile",
            str(profile_path),
            "--output",
            str(output_path),
            "--queue-db",
            str(tmp_path / "queue.sqlite3"),
            "--audit-log",
            str(tmp_path / "audit.jsonl"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text())
    assert payload["mode"] == "dry_run"
    assert payload["scan"]["new"] == 2
    assert payload["plan"]["counts"] == {
        "greenhouse": 1,
        "workday": 0,
        "unsupported": 0,
        "manual_only": 1,
    }
    assert payload["queue"]["count"] == 1
    queued_job = payload["queue"]["jobs"][0]
    assert queued_job["company"] == "Example"
    assert queued_job["state"] == "discovered"

    audit_lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(audit_lines) == 1
    audit_entry = json.loads(audit_lines[0])
    assert audit_entry["event"] == "dry_run_completed"
    assert audit_entry["payload"]["profile"]["contact"]["email"] == "[REDACTED]"
    assert audit_entry["payload"]["profile"]["resume"] == "[REDACTED]"
