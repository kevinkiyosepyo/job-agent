from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import greenhouse_handler


def test_inspect_application_fixture_inventories_fields_and_verifies_uploaded_resume():
    fixture_text = (ROOT / "fixtures" / "greenhouse.html").read_text()

    result = greenhouse_handler.inspect_html(
        fixture_text,
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
        expected_resume_basename="Kevin_Pyo_Resume.pdf",
    )

    assert result["page_type"] == "application"
    assert result["page_url"] == "https://job-boards.greenhouse.io/example/jobs/123"
    assert result["company"] == "Fixture Company"
    assert result["role"] == "Software Engineer Intern"
    assert result["location"] == "United States"
    assert result["uploaded_resume_verified"] is True
    assert result["manual_gate"] is None
    assert [field["label"] for field in result["fields"]] == [
        "First Name",
        "Last Name",
        "Email",
        "Phone",
        "Resume",
        "Work authorization",
        "Sponsorship",
    ]
    assert result["fields"][4] == {
        "label": "Resume",
        "name": "resume",
        "type": "file",
        "required": True,
    }


def test_inspect_html_fails_closed_on_greenhouse_email_verification_gate():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Please verify your email to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["manual_gate"] == {
        "type": "email_verification",
        "detail": "Email verification detected",
    }


def test_main_fails_closed_for_greenhouse_manual_gate_and_emits_json(capsys, tmp_path):
    fixture = tmp_path / "email-verification.html"
    fixture.write_text("<h1>Software Engineer Intern</h1><p>Please verify your email to continue.</p>")

    exit_code = greenhouse_handler.main([
        str(fixture),
        "--page-url",
        "https://job-boards.greenhouse.io/example/jobs/123",
    ])

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["safe_to_prepare"] is False
    assert payload["manual_gate"]["type"] == "email_verification"


def test_inspect_html_fails_closed_when_greenhouse_asks_to_confirm_email_address():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Confirm your email address to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["safe_to_prepare"] is False
    assert result["manual_gate"] == {
        "type": "email_verification",
        "detail": "Email verification detected",
    }


def test_inspect_html_fails_closed_on_greenhouse_assessment_gate():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Complete the required assessment to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["safe_to_prepare"] is False
    assert result["manual_gate"] == {
        "type": "assessment",
        "detail": "Assessment detected",
    }


def test_inspect_html_fails_closed_when_greenhouse_requires_a_skills_test():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Please complete the skills test to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["safe_to_prepare"] is False
    assert result["manual_gate"] == {
        "type": "assessment",
        "detail": "Assessment detected",
    }


def test_inspect_html_fails_closed_on_greenhouse_identity_verification_gate():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Identity verification is required to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["safe_to_prepare"] is False
    assert result["manual_gate"] == {
        "type": "identity_verification",
        "detail": "Identity verification detected",
    }


def test_inspect_html_fails_closed_when_greenhouse_asks_to_verify_identity():
    result = greenhouse_handler.inspect_html(
        "<h1>Software Engineer Intern</h1><p>Please verify your identity to continue.</p>",
        page_url="https://job-boards.greenhouse.io/example/jobs/123",
    )

    assert result["safe_to_prepare"] is False
    assert result["manual_gate"] == {
        "type": "identity_verification",
        "detail": "Identity verification detected",
    }
