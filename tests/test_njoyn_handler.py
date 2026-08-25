from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import njoyn_handler


def test_inspect_html_classifies_njoyn_listing_and_exposes_apply_entrypoint():
    fixture_text = (ROOT / "fixtures" / "njoyn_listing.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?job=fixture",
    )

    assert result == {
        "page_type": "listing",
        "surface": "listing",
        "page_url": "https://cgi.njoyn.com/corp/xweb/xweb.asp?job=fixture",
        "role": "Software Developer Intern",
        "company": "CGI Careers",
        "location": "San Diego, California",
        "fields": [],
        "entrypoint": {"apply_label": "Apply now", "apply_url": "/apply/fixture"},
        "uploaded_resume_verified": None,
        "parser_correction_required": False,
        "manual_gate": None,
        "confirmation_text": None,
        "safe_to_prepare": False,
    }


def test_inspect_html_inventories_njoyn_account_controls_and_fails_closed():
    fixture_text = (ROOT / "fixtures" / "njoyn_login_profile.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?login=fixture",
    )

    assert result["page_type"] == "account"
    assert result["surface"] == "account"
    assert result["fields"] == [
        {"name": "email", "type": "email", "label": "Email address"},
        {"name": "password", "type": "password", "label": "Password"},
    ]
    assert result["entrypoint"] == {"create_profile_label": "Create a profile"}
    assert result["manual_gate"] == {
        "type": "account_sign_in",
        "detail": "Sign in or create a profile required",
    }
    assert result["safe_to_prepare"] is False


def test_inspect_html_inventories_njoyn_privacy_surface_and_fails_closed():
    fixture_text = (ROOT / "fixtures" / "njoyn_privacy.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?privacy=fixture",
    )

    assert result["page_type"] == "privacy"
    assert result["surface"] == "privacy"
    assert result["role"] == "Privacy Notice"
    assert result["fields"] == [
        {
            "name": "privacy_acknowledged",
            "type": "checkbox",
            "label": "I acknowledge the notice",
        }
    ]
    assert result["manual_gate"] == {
        "type": "privacy_notice",
        "detail": "Privacy notice acknowledgement required",
    }
    assert result["safe_to_prepare"] is False


def test_inspect_html_inventories_njoyn_disclosures_and_fails_closed():
    fixture_text = (ROOT / "fixtures" / "njoyn_disclosures.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?disclosures=fixture",
    )

    assert result["page_type"] == "disclosures"
    assert result["surface"] == "disclosures"
    assert result["role"] == "Employment disclosures"
    assert result["fields"] == [
        {"name": "authorized", "type": "radio", "label": "Yes"},
        {"name": "authorized", "type": "radio", "label": "No"},
        {"name": "sponsorship", "type": "radio", "label": "Yes"},
        {"name": "sponsorship", "type": "radio", "label": "No"},
    ]
    assert result["manual_gate"] == {
        "type": "employment_disclosures",
        "detail": "Required employment disclosures must be answered",
    }
    assert result["safe_to_prepare"] is False


def test_inspect_html_inventories_njoyn_disability_surface_and_fails_closed():
    fixture_text = (ROOT / "fixtures" / "njoyn_disability.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?disability=fixture",
    )

    assert result["page_type"] == "disability"
    assert result["surface"] == "disability"
    assert result["role"] == "Voluntary Self-Identification of Disability"
    assert result["fields"] == [
        {
            "name": "disability",
            "type": "select",
            "label": "Voluntary Self-Identification of Disability",
        }
    ]
    assert result["manual_gate"] == {
        "type": "disability_disclosure",
        "detail": "Voluntary disability disclosure must be explicitly handled",
    }
    assert result["safe_to_prepare"] is False


def test_inspect_html_inventories_njoyn_resume_upload_and_verifies_attached_filename():
    fixture_text = (ROOT / "fixtures" / "njoyn_resume_upload.html").read_text()

    result = njoyn_handler.inspect_html(
        fixture_text,
        page_url="https://cgi.njoyn.com/corp/xweb/xweb.asp?resume=fixture",
        expected_resume_basename="Resume.pdf",
    )

    assert result["page_type"] == "resume_upload"
    assert result["surface"] == "resume-upload"
    assert result["role"] == "Resume upload"
    assert result["fields"] == [
        {"name": "resume", "type": "file", "label": "Resume"},
    ]
    assert result["uploaded_resume_verified"] is True
    assert result["manual_gate"] is None
    assert result["safe_to_prepare"] is False
