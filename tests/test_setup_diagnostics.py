from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import setup_diagnostics


def test_run_checks_reports_blocking_profile_issues_without_touching_browser(tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"email": "test@example.com"},
                "resume": {"primary": str(tmp_path / "missing-resume.pdf")},
            }
        )
    )

    calls: list[str] = []

    def fake_probe_browser(base_url: str) -> dict:
        calls.append(base_url)
        return {"status": "ready", "recoverable": False, "error_code": None}

    report = setup_diagnostics.run_checks(
        profile_path,
        browser_base_url="http://127.0.0.1:9222",
        probe_browser=fake_probe_browser,
        oauth_token_path=tmp_path / "missing-token.json",
    )

    assert report["status"] == "blocking"
    assert report["ready"] is False
    assert report["checks"]["profile"]["status"] == "blocking"
    assert report["checks"]["profile"]["error_code"] == "missing_resume_file"
    assert report["checks"]["browser"]["status"] == "skipped"
    assert calls == []


def test_main_can_skip_browser_and_still_report_ready_for_offline_setup(tmp_path, capsys):
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    oauth_token = tmp_path / "google_token.json"
    resume_path.write_text("resume fixture")
    oauth_token.write_text("token fixture")
    profile_path.write_text(
        json.dumps(
            {
                "contact": {"email": "test@example.com"},
                "resume": {"primary": str(resume_path)},
            }
        )
    )

    exit_code = setup_diagnostics.main(
        [
            "--profile",
            str(profile_path),
            "--oauth-token",
            str(oauth_token),
            "--skip-browser",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["checks"]["oauth"]["status"] == "ready"
    assert payload["checks"]["browser"]["status"] == "skipped"
    assert payload["checks"]["browser"]["error_code"] == "skipped_by_flag"
