"""Synthetic employer search shell with misleading prose (ASM pilot structure)."""
from prepare_job import prepare_saved_html

URL = "https://job-boards.greenhouse.io/example/jobs/1"
PAGE = '''<h1>Software Engineering Intern</h1>
<p>Work with brilliant engineers — your personal dream team!</p>
<form action="/search"><input type="search" name="q"></form>'''


def test_search_only_shell_does_not_invent_employer_or_location_from_prose():
    result = prepare_saved_html(html_text=PAGE, page_url=URL)
    assert result["company"] == ""
    assert result["location"] == ""
    assert result["role"] == "Software Engineering Intern"
    assert result["page_type"] == "listing"
    assert result["safe_to_prepare"] is result["submission_enabled"] is False


def test_manifest_shell_identity_does_not_turn_prose_into_employer_fields():
    from ats_preflight import inspect_greenhouse_html

    result = inspect_greenhouse_html(PAGE, page_url=URL)
    assert result["company"] == result["location"] == ""
    assert result["role"] == "Software Engineering Intern"


def test_explicit_greenhouse_title_company_survives_search_only_classification():
    result = prepare_saved_html(
        html_text='<title>Job Application for Software Engineering Intern at Example Employer</title>' + PAGE,
        page_url=URL,
    )
    assert result["company"] == "Example Employer"
    assert result["location"] == ""
