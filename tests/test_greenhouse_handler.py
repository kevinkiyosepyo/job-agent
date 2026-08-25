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
