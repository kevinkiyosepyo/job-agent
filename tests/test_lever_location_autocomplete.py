"""Synthetic Lever-shaped controls, not employer data or live binding evidence."""
from prepare_job import prepare_saved_html
from prepare_live_job import _questions_from_fields
import pytest


def test_duplicate_visible_inputs_do_not_establish_a_unique_pair():
    extra = '<input class="location-input" data-qa="location-input" name="location" type="text">'
    html = WIDGET.replace('<input id="dynamic-selected"', extra + '<input id="dynamic-selected"')
    result = prepare_saved_html(html_text=html, page_url=URL)
    assert [f['type'] for f in result['fields'] if f['name'] == 'location'] == ['text', 'text']

URL = 'https://jobs.lever.co/example/synthetic/apply'
WIDGET = '''<div class="application-question">
  <label class="application-label" for="dynamic-location">Current location</label>
  <div class="application-field">
    <input id="dynamic-location" class="location-input" data-qa="location-input"
           name="location" type="text" required>
    <input id="dynamic-selected" name="selectedLocation" type="hidden">
    <div class="dropdown-container"><div class="dropdown-results"></div></div>
  </div></div>'''


def test_paired_location_picker_kind_reaches_preparation_questions():
    result = prepare_saved_html(html_text=WIDGET, page_url=URL)
    question = next(q for q in _questions_from_fields(result) if q['required'])
    assert question == {'label': 'Current location', 'required': True, 'type': 'combobox'}
    assert result['submission_enabled'] is False
    assert next(f for f in result['fields'] if f['name'] == 'selectedLocation')['type'] == 'hidden'


@pytest.mark.parametrize('old,new', [
    ('data-qa="location-input"', ''),
    ('class="location-input"', 'class="plain-input"'),
    ('name="selectedLocation"', 'name="unrelated"'),
    ('class="dropdown-results"', 'class="unrelated"'),
    ('class="application-field"', 'class="unrelated"'),
    ('<input id="dynamic-selected"', '<input name="selectedLocation" type="hidden"><input id="dynamic-selected"'),
    ('<div class="dropdown-container">', '<div class="dropdown-container"></div><div class="dropdown-container">'),
])
def test_incomplete_or_ambiguous_schema_retains_original_kind(old, new):
    result = prepare_saved_html(html_text=WIDGET.replace(old, new), page_url=URL)
    assert next(f for f in result['fields'] if f['name'] == 'location')['type'] == 'text'


def test_pair_members_in_different_containers_are_not_associated():
    html = WIDGET.replace('<input id="dynamic-selected"',
                          '</div><div class="application-field"><input id="dynamic-selected"')
    result = prepare_saved_html(html_text=html, page_url=URL)
    assert next(f for f in result['fields'] if f['name'] == 'location')['type'] == 'text'


def test_snapshot_values_are_not_promoted_to_bound_answers():
    html = WIDGET.replace('type="text" required', 'type="text" value="Synthetic City" required')
    html = html.replace('type="hidden"', 'type="hidden" value="synthetic-unverified-location"')
    result = prepare_saved_html(html_text=html, page_url=URL)
    assert next(f for f in result['fields'] if f['name'] == 'location')['type'] == 'combobox'
    assert all('value' not in field and 'bound_values_verified' not in field for field in result['fields'])
    assert result['submission_enabled'] is False
