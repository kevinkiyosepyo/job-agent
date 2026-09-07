"""Synthetic native Lever select schemas; no live employer data or actions."""
from prepare_job import prepare_saved_html


def test_saved_lever_select_keeps_raw_option_values_separate_from_question():
    html = '''<li class="application-question">
      <div class="application-label">Graduation year<span>✱</span></div>
      <select name="cards[example][field0]" required>
        <option value="">Select...</option><option value=" next">Next year</option>
        <option value="later">Later</option>
      </select></li>'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert report.get("select_groups") == [{
        "id": None, "name": "cards[example][field0]", "label": "Graduation year",
        "type": "select", "required": True, "multiple": False, "disabled": False,
        "options": [{"label": "Select...", "value": "", "disabled": False},
                    {"label": "Next year", "value": " next", "disabled": False},
                    {"label": "Later", "value": "later", "disabled": False}],
        "source": "static_html", "bound_values_verified": False,
    }]
    assert report["submission_enabled"] is False
    assert report["fields"][0]["label"] == "Graduation year"


def test_optgroup_disabled_options_are_not_advertised_as_enabled():
    html = '''<label for="choices">Choose</label><select id="choices" multiple>
      <optgroup label="Unavailable" disabled><option value="a">A</option></optgroup>
      <option value="b" disabled>B</option><option value="c">C</option></select>'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    group = report["select_groups"][0]
    assert group["multiple"] is True
    assert [option["disabled"] for option in group["options"]] == [True, True, False]


def test_optional_option_end_tags_do_not_merge_neighbor_labels():
    html = '''<label for="school">School</label><select id="school">
      <option value="a">A<option value="b">B</select>'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert [option["label"] for option in report["select_groups"][0]["options"]] == ["A", "B"]


def test_option_display_label_attribute_wins_over_fallback_text():
    html = '''<select name="school"><option value="school-id" label="Public label">Fallback text</option></select>'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert report["select_groups"][0]["options"][0]["label"] == "Public label"


def test_adjacent_same_name_selects_remain_separate_static_definitions():
    html = '''<input name="before"><select name="same" disabled>
      <option selected value=" raw ">Raw</option><option>No value attribute</option></select>
      <textarea name="middle"></textarea><select name="same">
      <option value="b">B</option></select><input name="after">'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    groups = report["select_groups"]
    assert len(groups) == 2
    assert groups[0]["disabled"] is True
    assert groups[1]["disabled"] is False
    assert groups[0]["options"] == [{"label": "Raw", "value": " raw ", "disabled": False},
                                    {"label": "No value attribute", "value": None, "disabled": False}]
    assert groups[1]["options"] == [{"label": "B", "value": "b", "disabled": False}]
    assert all(group["source"] == "static_html" and not group["bound_values_verified"] for group in groups)
    assert all("selected" not in option for group in groups for option in group["options"])


def test_implied_optgroup_end_does_not_leak_disabled_to_next_group():
    html = '''<select name="choose"><optgroup disabled><option>A
        <optgroup><option>B</select>'''
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert report["select_groups"][0]["options"] == [
        {"label": "A", "value": None, "disabled": True},
        {"label": "B", "value": None, "disabled": False}]


def test_id_only_select_uses_inventory_name_fallback_without_claiming_raw_name():
    html = '<select id="only-id"><option value="x">X</option></select>'
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert report["select_groups"][0]["name"] == report["fields"][0]["name"] == "only-id"
    assert report["select_groups"][0]["id"] == "only-id"


def test_empty_select_name_retains_shared_inventory_fallback():
    html = '<select id="fallback" name=""></select><select name=""></select>'
    report = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    assert [(group["id"], group["name"]) for group in report["select_groups"]] == [("fallback", "fallback"), (None, "")]
