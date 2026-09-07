"""Synthetic scoped Lever headers based on the official Palantir /apply pilot."""
from prepare_job import prepare_saved_html

URL = "https://jobs.lever.co/example/1/apply"


def test_saved_lever_role_comes_from_posting_header_not_unrelated_headings():
    page = '''<h2>Unrelated site heading</h2>
      <div class="section posting-header"><h2>Software Engineer, <span>Internship</span></h2></div>
      <h2>Submit your application</h2><input name="name">'''
    result = prepare_saved_html(html_text=page, page_url=URL)
    assert result["role"] == "Software Engineer, Internship"
    assert result["submission_enabled"] is False


def test_saved_lever_location_uses_explicit_header_location_category():
    page = '''<div class="location">Unrelated navigation location</div>
      <div class="posting-header"><h2>Software Engineer, Internship</h2>
        <div class="posting-categories"><div class="sort-by-time posting-category location">Denver, <span>CO</span></div>
        <div class="posting-category department">Dev /</div></div></div>'''
    result = prepare_saved_html(html_text=page, page_url=URL)
    assert result["location"] == "Denver, CO"
    assert result["submission_enabled"] is False


def test_ambiguous_posting_headers_do_not_guess_an_identity():
    page = '<div class="posting-header"><h2>Role A</h2></div><div class="posting-header"><h2>Role B</h2></div>'
    assert prepare_saved_html(html_text=page, page_url=URL)["role"] == ""


def test_ambiguous_values_in_one_header_are_not_selected_by_position():
    page = '''<div class="posting-header"><h2>Role A</h2><h2>Role B</h2>
      <div class="posting-category location">City A</div>
      <div class="posting-category location">City B</div></div>'''
    result = prepare_saved_html(html_text=page, page_url=URL)
    assert result["role"] == result["location"] == ""


def test_scoped_heading_wins_over_unrelated_h1_and_preserves_legacy_fallback():
    page = '<h1>Careers</h1><div class="posting-header"><h2>Intern &amp; Engineer</h2></div>'
    assert prepare_saved_html(html_text=page, page_url=URL)["role"] == "Intern & Engineer"
    legacy = '<h1>Legacy intern role</h1><div class="sort-by-location">City</div>'
    result = prepare_saved_html(html_text=legacy, page_url=URL)
    assert (result["role"], result["location"]) == ("Legacy intern role", "City")


def test_inline_identity_text_preserves_original_adjacency_and_spacing():
    page = '''<div class="posting-header"><h2>Engineer (<span>Intern</span>ship) &amp; <b>Software</b> Engineering</h2>
      <div class="posting-category location"><span>Denver</span>, CO</div></div>'''
    result = prepare_saved_html(html_text=page, page_url=URL)
    assert result["role"] == "Engineer (Internship) & Software Engineering"
    assert result["location"] == "Denver, CO"
