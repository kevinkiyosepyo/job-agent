from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ats_preflight


def test_run_preflight_manifest_inspects_supported_fixture_pages():
    manifest = [
        {
            "platform": "greenhouse",
            "page_url": "https://job-boards.greenhouse.io/example/jobs/123",
            "html_path": str(ROOT / "fixtures" / "greenhouse.html"),
        },
        {
            "platform": "workday",
            "page_url": "https://example.wd1.myworkdayjobs.com/en-US/careers/job/123/apply",
            "html_path": str(ROOT / "fixtures" / "workday.html"),
        },
        {
            "platform": "lever",
            "page_url": "https://jobs.lever.co/example/123/apply",
            "html_path": str(ROOT / "fixtures" / "lever_application.html"),
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
        },
        {
            "platform": "oracle",
            "page_url": "https://careers.example.com/job/123/apply",
            "html_path": str(ROOT / "fixtures" / "oracle_application.html"),
            "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
        },
    ]

    report = ats_preflight.run_preflight_manifest(manifest)

    assert report["summary"] == {
        "target_count": 4,
        "application_count": 4,
        "confirmation_count": 0,
        "manual_gate_count": 0,
        "failure_count": 0,
    }
    assert [result["platform"] for result in report["results"]] == [
        "greenhouse",
        "workday",
        "lever",
        "oracle",
    ]
    assert report["results"][0]["role"] == "Software Engineer Intern"
    assert report["results"][0]["required_fields"] == [
        "First Name",
        "Last Name",
        "Email",
        "Phone",
        "Resume",
        "Work authorization",
        "Sponsorship",
    ]
    assert report["results"][1]["steps"] == [
        "My Information",
        "My Experience",
        "Application Questions",
        "Review",
    ]
    assert report["results"][2]["uploaded_resume_verified"] is True
    assert report["results"][3]["country_valid"] is True


def test_inspect_workday_live_entrypoint_fixture_detects_rendered_apply_surface():
    target = {
        "platform": "workday",
        "page_url": "https://tencent.wd1.myworkdayjobs.com/en-US/Tencent_Careers/job/Software-Engineering-Intern_R107162-1",
        "html_path": str(ROOT / "fixtures" / "workday_live_entrypoint.html"),
    }

    result = ats_preflight.inspect_target(target)

    assert result["platform"] == "workday"
    assert result["page_type"] == "listing"
    assert result["role"] == "Software Engineering Intern"
    assert result["location"] == "United Kingdom-London"
    assert result["entrypoint"] == {
        "apply_label": "Apply",
        "sign_in_label": "Sign In",
        "requisition_id": "R107162",
    }
    assert result["fields"] == []


def test_inspect_workday_target_uses_executable_handler_safety_contract():
    target = {
        "platform": "workday",
        "page_url": "https://example.wd1.myworkdayjobs.com/en-US/careers/job/1",
        "html_path": str(ROOT / "fixtures" / "workday_parse_issues.html"),
        "expected_resume_basename": "Kevin_Pyo_Resume.pdf",
    }

    result = ats_preflight.inspect_target(target)

    assert result["platform"] == "workday"
    assert result["uploaded_resume_verified"] is True
    assert result["safe_to_prepare"] is False
    assert [issue["field"] for issue in result["parse_issues"]] == ["school", "gpa"]
    assert result["save_draft_available"] is True


def test_inspect_oracle_live_entrypoint_fixture_detects_apply_button_without_false_form_fields():
    target = {
        "platform": "oracle",
        "page_url": "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/334348",
        "html_path": str(ROOT / "fixtures" / "oracle_live_entrypoint.html"),
    }

    result = ats_preflight.inspect_target(target)

    assert result["platform"] == "oracle"
    assert result["page_type"] == "listing"
    assert result["role"] == "OH Product Manager Intern - OVIP"
    assert result["location"] == "Kansas City, MO, United States"
    assert result["entrypoint"] == {"apply_label": "Apply Now"}
    assert result["fields"] == []
    assert result["issues"] == []
