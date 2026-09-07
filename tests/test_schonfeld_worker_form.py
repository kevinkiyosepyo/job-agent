"""Learned map and JavaScript-reader tests using offline fixtures only."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

URL = "https://job-boards.greenhouse.io/schonfeld/jobs/8171772"


def test_schonfeld_exact_map_keeps_all_required_controls_and_dynamic_education():
    import tenant_field_maps

    try:
        mapping = tenant_field_maps.resolve_field_map(page_url=URL, platform="greenhouse")
    except tenant_field_maps.FieldMapError:
        pytest.fail("the exact observed Schonfeld form has no learned map")
    assert mapping["tenant"] == "schonfeld"
    step = mapping["steps"]["application"]
    assert set(step["required_fields"]) == {
        "first_name", "last_name", "email", "country", "phone", "location", "resume",
        "school", "degree", "discipline", "education_start_month", "education_start_year",
        "education_end_month", "education_end_year", "gpa", "current_degree",
        "work_authorization", "sponsorship_now", "sponsorship_future",
    }
    assert step["controls"]["gpa"] == {"selector": "#question_68930283", "operation": "replace_text"}
    assert step["controls"]["school"]["selector"] == "input[id^='school--']"
    assert step["controls"]["sponsorship_now"]["selector"] == "#question_68930287"
    assert step["controls"]["sponsorship_future"]["selector"] == "#question_68930288"
    assert mapping["steps"]["review"]["required_conditions"] == ["authoritative_review"]
    for suffix in ["0", "/other", "?other=1", "#other"]:
        with pytest.raises(tenant_field_maps.FieldMapError):
            tenant_field_maps.resolve_field_map(page_url=URL + suffix, platform="greenhouse")


def test_readonly_control_script_observes_exact_react_choice_not_search_text():
    import json
    import subprocess
    import schonfeld_form

    script = schonfeld_form.control_expression("#country")
    fixture = r"""
    const element = {
        id: 'country', value: '', disabled: false, validity: {valid:true},
        __reactProps$fixture: {value: ''},
        __reactFiber$fixture: {memoizedProps: {selectProps: {inputId:'country', value:[{value:'us',label:'United States +1'}]}}, return:null},
        getAttribute: name => name === 'role' ? 'combobox' : 'false',
        getBoundingClientRect: () => ({left:0,top:0,width:10,height:10}),
        getClientRects: () => [1], contains: () => false,
        closest: () => ({querySelector: () => ({innerText:'+1'})})
    };
    global.document = {querySelectorAll: () => [element], elementFromPoint: () => element};
    global.getComputedStyle = () => ({display:'block',visibility:'visible',opacity:'1'});
    """
    result = subprocess.run(["node", "-e", fixture + "console.log(JSON.stringify(" + script + "));"], capture_output=True, text=True, check=True)
    state = json.loads(result.stdout)
    assert state["value"] == "+1", "search text must not substitute for selected value"
    assert state["choice"] == [{"value": "us", "label": "United States +1"}]
    assert state["bound"] is True
