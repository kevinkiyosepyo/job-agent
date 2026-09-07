"""Synthetic minimized Lever card markup, based on public pilot structure.

No employer application data or browser is used. Question/option text is public
schema evidence, not a claim that a form was filled or saved.
"""
from prepare_job import prepare_saved_html


def test_saved_lever_preparation_labels_custom_text_question():
    # Belvedere public /apply: application-label div is not a label[for].
    html = '''<li class="application-question custom-question"><div>
      <div class="application-label full-width text"><div class="text">
        City<span class="required">✱</span></div></div>
      <div class="application-field full-width required-field">
        <input required="required" class="card-field-input" type="text"
          placeholder="Type your response" value="" name="cards[synthetic][field1]">
      </div></div></li>'''
    result = prepare_saved_html(html_text=html,
        page_url="https://jobs.lever.co/example/1/apply")
    assert result["platform"] == "lever"
    assert result["submission_enabled"] is False
    assert result["fields"] == [{"label": "City", "name": "cards[synthetic][field1]",
                                 "type": "text", "required": True}]


def test_saved_lever_preparation_keeps_radio_options_distinct_from_question():
    page = '''<li class="application-question custom-question">
      <div class="application-label">Are you legally authorized?*</div>
      <div class="application-field">
        <label><input type="radio" name="cards[synthetic][field0]" value=" yes" required>
          <span class="card-field-list-item-label">Yes</span></label>
        <label><input type="radio" name="cards[synthetic][field0]" value="no" required>
          <span class="card-field-list-item-label">No</span></label>
      </div></li>'''
    result = prepare_saved_html(html_text=page,
        page_url="https://jobs.lever.co/example/1/apply")
    assert result.get("choice_groups") == [{
        "name": "cards[synthetic][field0]", "label": "Are you legally authorized?",
        "type": "radio", "required": True,
        "options": [{"label": "Yes", "value": " yes", "disabled": False}, {"label": "No", "value": "no", "disabled": False}],
        "source": "static_html", "bound_values_verified": False,
    }]
    assert result["submission_enabled"] is False


def test_saved_lever_preparation_preserves_checkbox_options_and_question():
    # Minimized synthetic version of the actual Palantir language group.
    page = '''<li class="application-question custom-question">
      <div class="application-label full-width multiple-select"><div class="text">
        Languages (check all that apply)<span class="required">✱</span></div></div>
      <div class="application-field required-field"><ul>
        <li><label><input type="checkbox" name="cards[synthetic][field0]" value=" EN" required />
          <span class="application-answer-alternative">English</span></label></li>
        <li><label><input type="checkbox" name="cards[synthetic][field0]" value="JP" required />
          <span class="application-answer-alternative">Japanese</span></label></li>
      </ul></div></li>'''
    result = prepare_saved_html(html_text=page, page_url="https://jobs.lever.co/example/1/apply")
    assert result.get("choice_groups") == [{
        "name": "cards[synthetic][field0]", "label": "Languages (check all that apply)",
        "type": "checkbox", "required": True,
        "options": [{"label": "English", "value": " EN"}, {"label": "Japanese", "value": "JP"}],
        "source": "static_html", "bound_values_verified": False,
    }]
    assert result["submission_enabled"] is False


def test_checkbox_schema_does_not_merge_different_control_types_with_shared_name():
    # Synthetic drift case: do not assign checkbox options to a radio group.
    page = '''<li class="application-question"><div class="application-label">Pick</div>
      <label><input type="radio" name="shared" value="r">Radio option</label>
      <label><input type="checkbox" name="shared" value="c">Checkbox option</label></li>'''
    result = prepare_saved_html(html_text=page, page_url="https://jobs.lever.co/example/1/apply")
    assert [(group["type"], group["options"]) for group in result["choice_groups"]] == [
        ("radio", [{"label": "Radio option", "value": "r", "disabled": False}]),
        ("checkbox", [{"label": "Checkbox option", "value": "c"}]),
    ]
