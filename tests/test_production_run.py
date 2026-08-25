from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import orchestrator
import production_run
import sources


def _write_profile(tmp_path: Path) -> Path:
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_text("fixture resume")
    profile_path.write_text(
        json.dumps(
            {
                "name": {"full": "Test User"},
                "contact": {"email": "test@example.com", "phone": "555-1111"},
                "resume": {"primary": str(resume_path)},
                "preferences": {
                    "target_roles": ["Software Engineer Intern"],
                    "target_timelines": ["Summer 2027"],
                    "location_preference": "Remote or anywhere in U.S.",
                },
            }
        )
    )
    return profile_path



def test_main_runs_sources_then_orchestrator_and_persists_all_artifacts(tmp_path, monkeypatch, capsys):
    profile_path = _write_profile(tmp_path)

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)
    monkeypatch.setattr(
        sources,
        "fetch_greenhouse_jobs",
        lambda token, **kwargs: [
            {
                "company": "Example",
                "role": "Software Engineer Intern, Summer 2027",
                "url": "https://job-boards.greenhouse.io/example/jobs/123?utm_source=linkedin",
                "location": "Remote",
                "source": "Greenhouse public API",
                "updated_at": "2026-08-23T00:00:00Z",
            }
        ],
    )

    workspace = tmp_path / "runtime"
    exit_code = production_run.main(
        [
            "--greenhouse",
            "example",
            "--profile",
            str(profile_path),
            "--workspace",
            str(workspace),
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "production_safe_dry_run"
    assert payload["source_exit_code"] == 0
    assert payload["orchestrator_exit_code"] == 0

    candidates = json.loads((workspace / "candidates.json").read_text())
    assert candidates == [
        {
            "company": "Example",
            "role": "Software Engineer Intern, Summer 2027",
            "url": "https://job-boards.greenhouse.io/example/jobs/123",
            "location": "Remote",
            "source": "Greenhouse public API",
            "updated_at": "2026-08-23T00:00:00Z",
        }
    ]

    source_report = json.loads((workspace / "sources-report.json").read_text())
    assert source_report["source_health_status"] == "healthy"

    orchestrator_report = json.loads((workspace / "orchestrator-report.json").read_text())
    assert orchestrator_report["mode"] == "dry_run"
    assert orchestrator_report["queue"]["count"] == 1
