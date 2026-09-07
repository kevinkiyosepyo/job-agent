"""Synthetic minimized Greenhouse fieldsets; no employer data or live actions."""
from prepare_job import prepare_saved_html


def test_saved_greenhouse_fieldset_preserves_question_and_raw_checkbox_options():
    page = '''<fieldset class="checkbox" id="question_synthetic[]" aria-required="true">
      <legend class="label checkbox__description">In which settings have you used C++?
        Select all that apply. <span class="required">*</span></legend>
      <div><input type="checkbox" id="choice_one" name="question_synthetic[]" value=" code1" required>
        <label for="choice_one">Personal Projects</label></div>
      <div><input type="checkbox" id="choice_two" name="question_synthetic[]" value="code2" required>
        <label for="choice_two">Classwork</label></div>
    </fieldset>'''
    result = prepare_saved_html(html_text=page, page_url="https://job-boards.greenhouse.io/example/jobs/1")
    assert result.get("choice_groups") == [{
        "fieldset_id": "question_synthetic[]", "name": "question_synthetic[]",
        "label": "In which settings have you used C++? Select all that apply.",
        "type": "checkbox", "required": True,
        "options": [{"id": "choice_one", "label": "Personal Projects", "value": " code1"},
                    {"id": "choice_two", "label": "Classwork", "value": "code2"}],
        "source": "static_html", "bound_values_verified": False,
    }]
    assert [field["label"] for field in result["fields"]] == ["Personal Projects", "Classwork"]
    assert result["submission_enabled"] is False


def test_fieldset_aria_requirement_is_preserved_without_native_required_inputs():
    page = '''<fieldset aria-required="true"><legend>Synthetic topic</legend>
      <label><input type="checkbox" name="topics" value="a">First option</label></fieldset>'''
    result = prepare_saved_html(html_text=page, page_url="https://job-boards.greenhouse.io/example/jobs/1")
    assert result["choice_groups"][0]["required"] is True
