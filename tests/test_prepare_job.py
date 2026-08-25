from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import prepare_job


def test_prepare_saved_html_dispatches_to_supported_ats_handlers():
    scenarios = [
        {
            "fixture": "greenhouse.html",
            "page_url": "https://job-boards.greenhouse.io/example/jobs/123",
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
            "platform": "greenhouse",
            "role": "Software Engineer Intern",
            "page_type": "application",
        },
        {
            "fixture": "workday.html",
            "page_url": "https://example.wd1.myworkdayjobs.com/en-US/careers/job/Software-Engineering-Intern_R123",
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
            "platform": "workday",
            "role": "Software Engineering Intern — Workday Fixture",
            "page_type": "application",
        },
        {
            "fixture": "lever_application.html",
            "page_url": "https://jobs.lever.co/example/1/apply",
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
            "platform": "lever",
            "role": "Data Scientist Intern",
            "page_type": "application",
        },
        {
            "fixture": "oracle_application.html",
            "page_url": "https://careers.example.com/job/123/apply",
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
            "platform": "oracle",
            "role": "Software Engineer Intern",
            "page_type": "application",
        },
    ]

    for scenario in scenarios:
        result = prepare_job.prepare_saved_html(
            html_text=(ROOT / "fixtures" / scenario["fixture"]).read_text(),
            page_url=scenario["page_url"],
            expected_resume_basename=scenario["expected_resume_basename"],
        )

        assert result["platform"] == scenario["platform"]
        assert result["page_type"] == scenario["page_type"]
        assert result["role"] == scenario["role"]
        assert result["submission_enabled"] is False
        assert result["page_url"] == scenario["page_url"]


def test_main_fails_closed_with_machine_readable_error_for_unsupported_ats(tmp_path, capsys):
    output_path = tmp_path / "prepare-job.json"

    exit_code = prepare_job.main([
        str(ROOT / "fixtures" / "greenhouse.html"),
        "--page-url",
        "https://example.com/custom/apply",
        "--output",
        str(output_path),
    ])

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "error": "Unsupported ATS for URL: https://example.com/custom/apply",
        "page_url": "https://example.com/custom/apply",
        "submission_enabled": False,
    }
    assert not output_path.exists()
