from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fixture_e2e


def test_run_greenhouse_fixture_flow_prepares_queue_answer_coverage_plan_and_evidence(tmp_path):
    profile = {"education": {"graduation_season": "Spring 2028"}}
    result = fixture_e2e.run_fixture_flow(
        fixture_path=ROOT / "fixtures" / "greenhouse.html",
        candidate={
            "company": "Fixture Company",
            "role": "Software Engineer Intern",
            "url": "https://job-boards.greenhouse.io/fixture/jobs/123",
            "ats_platform": "Greenhouse",
        },
        profile=profile,
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://job-boards.greenhouse.io/fixture/applications/123/confirmation",
        confirmation_text="Thanks for applying. We've received your application.",
    )

    assert result["submission_enabled"] is False
    assert result["queue_job"]["state"] == "prepared"
    assert result["queue_job"]["ats_platform"] == "Greenhouse"
    assert result["answer_coverage"]["known"] == [{
        "question": "What is your expected graduation season?",
        "question_key": "graduation_season",
        "source": "profile",
    }]
    assert result["plan"]["platform"] == "greenhouse"
    assert result["plan"]["uploaded_resume_verified"] is True
    assert result["evidence_artifact"]["tracker"]["values"][1] == "Submitted - Pending Response"
    assert result["evidence_artifact"]["reconciliation"]["consistent"] is True


def test_run_workday_fixture_flow_prepares_non_submitting_wizard_plan_and_evidence(tmp_path):
    profile = {"education": {"graduation_season": "Spring 2028"}}

    result = fixture_e2e.run_workday_fixture_flow(
        fixture_path=ROOT / "fixtures" / "workday.html",
        candidate={
            "company": "Workday Fixture Company",
            "role": "Software Engineering Intern",
            "url": "https://fixture.wd1.myworkdayjobs.com/en-US/Careers/job/Test/123",
            "ats_platform": "Workday",
        },
        profile=profile,
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://fixture.wd1.myworkdayjobs.com/en-US/Careers/confirmation",
        confirmation_text="Your application has been received. Reference ID: WD-123",
    )

    assert result["submission_enabled"] is False
    assert result["queue_job"]["state"] == "prepared"
    assert result["queue_job"]["ats_platform"] == "Workday"
    assert result["answer_coverage"]["known"][0]["source"] == "profile"
    assert result["plan"]["platform"] == "workday"
    assert result["plan"]["safe_to_prepare"] is True
    assert result["plan"]["uploaded_resume_verified"] is True
    assert result["evidence_artifact"]["reconciliation"]["consistent"] is True


def test_run_lever_fixture_flow_prepares_non_submitting_plan_and_evidence(tmp_path):
    profile = {"education": {"graduation_season": "Spring 2028"}}

    result = fixture_e2e.run_lever_fixture_flow(
        fixture_path=ROOT / "fixtures" / "lever_application.html",
        candidate={
            "company": "Lever Fixture Company",
            "role": "Data Scientist Intern",
            "url": "https://jobs.lever.co/fixture/123",
            "ats_platform": "Lever",
        },
        profile=profile,
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://jobs.lever.co/fixture/123/confirmation",
        confirmation_text="Thanks for applying. We've received your application.",
    )

    assert result["submission_enabled"] is False
    assert result["queue_job"]["state"] == "prepared"
    assert result["queue_job"]["ats_platform"] == "Lever"
    assert result["answer_coverage"]["known"][0]["source"] == "profile"
    assert result["plan"]["platform"] == "lever"
    assert result["plan"]["uploaded_resume_verified"] is True
    assert result["evidence_artifact"]["reconciliation"]["consistent"] is True


def test_run_oracle_fixture_flow_prepares_non_submitting_plan_and_evidence(tmp_path):
    profile = {"education": {"graduation_season": "Spring 2028"}}

    result = fixture_e2e.run_oracle_fixture_flow(
        fixture_path=ROOT / "fixtures" / "oracle_application.html",
        candidate={
            "company": "Oracle Fixture Company",
            "role": "Software Engineer Intern",
            "url": "https://careers.example.com/job/123/apply",
            "ats_platform": "Oracle",
        },
        profile=profile,
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://careers.example.com/job/123/apply/confirmation",
        confirmation_text="Your application has been received.",
    )

    assert result["submission_enabled"] is False
    assert result["queue_job"]["state"] == "prepared"
    assert result["queue_job"]["ats_platform"] == "Oracle"
    assert result["answer_coverage"]["known"][0]["source"] == "profile"
    assert result["plan"]["platform"] == "oracle"
    assert result["plan"]["uploaded_resume_verified"] is True
    assert result["plan"]["country_valid"] is True
    assert result["evidence_artifact"]["reconciliation"]["consistent"] is True


def test_run_njoyn_fixture_flow_prepares_resume_plan_and_parser_review_evidence(tmp_path):
    result = fixture_e2e.run_njoyn_fixture_flow(
        fixture_path=ROOT / "fixtures" / "njoyn_resume_upload.html",
        parser_fixture_path=ROOT / "fixtures" / "njoyn_parsed_profile.html",
        candidate={
            "company": "CGI Fixture Company",
            "role": "Software Developer Intern",
            "url": "https://cgi.njoyn.com/CL3/xweb/xweb.asp?CLID=1&page=jobdetails&jobid=123",
            "ats_platform": "njoyn",
        },
        profile={"education": {"graduation_season": "Spring 2028"}},
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://cgi.njoyn.com/CL3/xweb/xweb.asp?confirmation=1",
        confirmation_text="Your application has been received. Reference: CGI-FIXTURE-001.",
    )

    assert result["submission_enabled"] is False
    assert result["queue_job"]["state"] == "prepared"
    assert result["plan"]["platform"] == "njoyn"
    assert result["plan"]["uploaded_resume_verified"] is True
    assert result["parser_review"]["page_type"] == "parsed_profile"
    assert result["parser_review"]["parser_correction_required"] is False
    assert result["evidence_artifact"]["reconciliation"]["consistent"] is True


def test_run_njoyn_fixture_flow_blocks_parser_mismatch_until_correction_is_recorded(tmp_path):
    result = fixture_e2e.run_njoyn_fixture_flow(
        fixture_path=ROOT / "fixtures" / "njoyn_resume_upload.html",
        parser_fixture_path=ROOT / "fixtures" / "njoyn_parsed_profile_mismatch.html",
        candidate={
            "company": "CGI Fixture Company",
            "role": "Software Developer Intern",
            "url": "https://cgi.njoyn.com/CL3/xweb/xweb.asp?CLID=1&page=jobdetails&jobid=123",
            "ats_platform": "njoyn",
        },
        profile={"education": {"graduation_season": "Spring 2028"}},
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://cgi.njoyn.com/CL3/xweb/xweb.asp?confirmation=1",
        confirmation_text="Your application has been received. Reference: CGI-FIXTURE-001.",
    )

    assert result["parser_review"]["parser_correction_required"] is True
    assert result["parser_repair_evidence"] == {
        "status": "blocked",
        "required_corrections": ["school"],
        "resolved_corrections": [],
        "unresolved_corrections": ["school"],
        "safe_to_continue": False,
    }
    assert result["submission_enabled"] is False


def test_run_njoyn_fixture_flow_accepts_all_recorded_parser_corrections(tmp_path):
    result = fixture_e2e.run_njoyn_fixture_flow(
        fixture_path=ROOT / "fixtures" / "njoyn_resume_upload.html",
        parser_fixture_path=ROOT / "fixtures" / "njoyn_parsed_profile_mismatch.html",
        parser_corrections=["school"],
        candidate={
            "company": "CGI Fixture Company",
            "role": "Software Developer Intern",
            "url": "https://cgi.njoyn.com/CL3/xweb/xweb.asp?CLID=1&page=jobdetails&jobid=123",
            "ats_platform": "njoyn",
        },
        profile={"education": {"graduation_season": "Spring 2028"}},
        questions=[{"label": "What is your expected graduation season?", "required": True}],
        expected_resume_basename="Resume.pdf",
        queue_db_path=tmp_path / "queue.db",
        plan_dir=tmp_path / "plans",
        confirmation_url="https://cgi.njoyn.com/CL3/xweb/xweb.asp?confirmation=1",
        confirmation_text="Your application has been received. Reference: CGI-FIXTURE-001.",
    )

    assert result["parser_repair_evidence"] == {
        "status": "resolved",
        "required_corrections": ["school"],
        "resolved_corrections": ["school"],
        "unresolved_corrections": [],
        "safe_to_continue": True,
    }
