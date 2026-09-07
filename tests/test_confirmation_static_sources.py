"""Synthetic reduced bootstrapped Greenhouse public-page regression."""
import pytest
import pipeline
from prepare_job import prepare_saved_html


def test_bootstrap_confirmation_message_is_not_employer_confirmation():
    # Shape and confirmation_message key observed in official Anduril page.
    # This is synthetic minimized markup, NOT a submitted application.
    page = r'''<h1>Synthetic Software Engineer Intern</h1>
      <form><label>First Name<input name="first_name" required></label></form>
      <script>window.__bootstrap = {"confirmation_message":
      "\u003ch1\u003eThank you for applying.\u003c/h1\u003e\n\u003cp\u003eYour application has been received.\u003c/p\u003e"};</script>'''
    url = "https://job-boards.greenhouse.io/example/jobs/123"
    result = prepare_saved_html(html_text=page, page_url=url)
    assert result["page_type"] == "application"
    assert result["confirmation_text"] is None
    assert result["submission_enabled"] is False
    with pytest.raises(ValueError, match="confirmation"):
        pipeline.validate_confirmation_evidence(confirmation_url=url, confirmation_text=page)
