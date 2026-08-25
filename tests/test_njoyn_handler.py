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
