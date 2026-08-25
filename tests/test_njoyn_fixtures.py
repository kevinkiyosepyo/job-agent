from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def test_sanitized_njoyn_fixture_set_covers_each_verified_application_surface():
    expected_surfaces = {
        "njoyn_listing.html": "Apply now",
        "njoyn_login_profile.html": "Create a profile",
        "njoyn_privacy.html": "Privacy Notice",
        "njoyn_disclosures.html": "Work authorization",
        "njoyn_disability.html": "Voluntary Self-Identification of Disability",
        "njoyn_resume_upload.html": "Resume upload",
        "njoyn_parsed_profile.html": "Parsed profile",
        "njoyn_referral.html": "How did you hear about us?",
        "njoyn_questionnaire.html": "Application questionnaire",
        "njoyn_confirmation.html": "Application received",
    }

    forbidden_values = (
        "kevin",
        "kpyo@ucsd.edu",
        "kevinkpyo@gmail.com",
        "571-435-5734",
        "10256 eagle nest",
    )

    for filename, expected_marker in expected_surfaces.items():
        fixture = FIXTURES / filename
        assert fixture.is_file(), filename
        html = fixture.read_text(encoding="utf-8")
        assert expected_marker in html
        assert all(value not in html.lower() for value in forbidden_values), filename
