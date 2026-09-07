"""Synthetic modern Greenhouse controls, not real employer/application data."""
from greenhouse_handler import inspect_html


def test_scoped_react_multi_container_is_not_lost_as_plain_combobox():
    html = '''<h1>Software Engineering Intern</h1>
    <label for="range[]">Choose a range</label>
    <div class="select__value-container select__value-container--is-multi">
      <div><input id="range[]" role="combobox" aria-required="true"></div>
    </div>'''
    report = inspect_html(html, page_url="https://job-boards.greenhouse.io/example/jobs/123")
    assert report["control_hints"].get("react_multiselects") == [{
        "id": "range[]", "label": "Choose a range", "required": True,
        "source": "static_html", "bound_values_verified": False,
        "options_verified": False,
    }]
    assert report["fields"][0]["type"] == "combobox"


def test_ambiguous_id_does_not_generate_a_target_hint():
    html = '''<div class="select__value-container--is-multi">
        <input id="duplicated" role="combobox"></div>
        <input id="duplicated" role="combobox">'''
    report = inspect_html(html, page_url="https://job-boards.greenhouse.io/example/jobs/123")
    assert report["control_hints"].get("react_multiselects", []) == []


def test_multiselect_hint_does_not_guess_from_brackets_or_nearby_controls():
    html = '''<div class="select__value-container--is-multi">
        <label for="actual[]">Real multi</label><input id="actual[]" role="combobox" aria-required="true">
        <input required aria-hidden="true" value="">
      </div>
      <input id="brackets[]" role="combobox">
      <div class="not-select__value-container--is-multi"><input id="suffix" role="combobox"></div>
      <input id="own" role="combobox" class="select__value-container--is-multi">
      <div class="select__value-container--is-multi"><input role="combobox"></div>
      <select id="native" multiple><option value="x">X</option></select>'''
    report = inspect_html(html, page_url="https://job-boards.greenhouse.io/example/jobs/123")
    assert [hint["id"] for hint in report["control_hints"]["react_multiselects"]] == ["actual[]"]
    assert any(field["name"] == "" and field["required"] for field in report["fields"])
    assert len(report["fields"]) == 7
