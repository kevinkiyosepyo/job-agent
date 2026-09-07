"""Synthetic modern Greenhouse header markup based on the DRW saved pilot."""
from prepare_job import prepare_saved_html

URL = "https://job-boards.greenhouse.io/example/jobs/1"
PAGE = '''<p>Wrong Corp — Wrong location</p>
<div class="job__header"><div class="job__title"><h1>Software Developer Intern</h1>
<div class="job__location"><svg><title>Location icon</title></svg>
<div><span>Example</span>ville, XX</div></div></div></div>
<form><input name="email" type="email" required></form>'''


def test_modern_job_location_overrides_unrelated_body_prose():
    result = prepare_saved_html(html_text=PAGE, page_url=URL)
    assert result["location"] == "Exampleville, XX"
    assert result["role"] == "Software Developer Intern"
    assert result["submission_enabled"] is False


def test_manifest_preflight_preserves_the_same_scoped_modern_location():
    from ats_preflight import inspect_greenhouse_html

    result = inspect_greenhouse_html(PAGE, page_url=URL)
    assert result["location"] == "Exampleville, XX"


def test_ambiguous_modern_location_does_not_fall_back_to_prose():
    value = '<div><span>Example</span>ville, XX</div>'
    ambiguous_pages = [PAGE + '<div class="job__header"></div>',
                       PAGE.replace(value, value + '<div>Second city</div>'),
                       PAGE.replace(value, 'Unscoped raw city')]
    for page in ambiguous_pages:
        assert prepare_saved_html(html_text=page, page_url=URL)["location"] == ""


def test_legacy_location_is_retained_without_a_modern_header():
    result = prepare_saved_html(html_text='<p>Example — Legacy city</p>', page_url=URL)
    assert result["location"] == "Legacy city"


def test_search_only_shell_still_suppresses_header_location():
    page = PAGE.replace('<form><input name="email" type="email" required></form>',
                        '<form action="/search"><input type="search" name="q"></form>')
    result = prepare_saved_html(html_text=page, page_url=URL)
    assert result["location"] == ""
    assert result["page_type"] == "listing"
    assert result["safe_to_prepare"] is False
