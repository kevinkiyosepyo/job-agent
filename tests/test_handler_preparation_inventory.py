"""Pure HTML inventory fixtures: no browser or network."""
import importlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize('handler', ['greenhouse_handler','workday_handler','njoyn_handler'])
def test_inventory_includes_sibling_labels_and_aria_required_controls(handler):
    html='''<main><div><input id="q1" name="opaque" aria-required="true">
    <label for="q1">Availability <span>*</span></label></div>
    <div><span id="country-label">Country</span><span id="country-note">of residence</span>
    <button id="country" role="combobox" aria-labelledby="country-label country-note" aria-required="true">Select One</button></div>
    <div><label>Referral detail</label><textarea id="details" required></textarea></div></main>'''
    result=importlib.import_module(handler).inspect_html(html, page_url='https://fixture.invalid/apply')
    assert result['fields'] == [
        {'name':'opaque','type':'text','label':'Availability','required':True},
        {'name':'country','type':'combobox','label':'Country of residence','required':True},
        {'name':'details','type':'textarea','label':'Referral detail','required':True},
    ]


@pytest.mark.parametrize('handler', ['greenhouse_handler','workday_handler','njoyn_handler'])
def test_conditional_child_is_included_on_fresh_inventory_not_cached(handler):
    inspect=importlib.import_module(handler).inspect_html
    parent='<label for="source">Source</label><select id="source" required><option>Social Media</option></select>'
    child='<label for="source_detail">Social platform</label><input id="source_detail" aria-required="true">'
    initial=inspect(parent,page_url='https://fixture.invalid/apply')
    refreshed=inspect(parent+child,page_url='https://fixture.invalid/apply')
    assert [f['name'] for f in initial['fields']] == ['source']
    assert [f['name'] for f in refreshed['fields']] == ['source','source_detail']
    assert refreshed['fields'][-1]['required'] is True
