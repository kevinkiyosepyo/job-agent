"""Synthetic reduced pilot schema: known fact is not a selectable answer."""
from answer_coverage import build_coverage_matrix
from prepare_job import prepare_saved_html
from prepare_live_job import _questions_from_fields


def test_native_select_missing_canonical_answer_cannot_be_marked_known():
    html = '''<li class="application-question"><div class="application-label">
      Please tell us how you heard about this internship opportunity.</div>
      <select name="source" required><option value="">Select...</option>
      <option value="event">Company Event</option><option value="other">Other</option></select></li>'''
    inspection = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    matrix = build_coverage_matrix(
        profile={"screening_defaults": {"how_did_you_hear": "Social Media"}},
        questions=_questions_from_fields(inspection))
    assert matrix["known"] == []
    assert matrix["human_required"][0]["reason"] == "answer_not_in_native_options"


def _matrix_for_select(select_markup):
    html = '<label for="source">How did you hear about us?</label>' + select_markup
    inspection = prepare_saved_html(html_text=html, page_url="https://jobs.lever.co/example/1/apply")
    return build_coverage_matrix(profile={"screening_defaults": {"how_did_you_hear": "Social Media"}},
                                 questions=_questions_from_fields(inspection))


def test_one_exact_native_option_is_fact_coverage_not_bound_state():
    matrix = _matrix_for_select('<select id="source" required><option value="social">Social Media</option></select>')
    assert matrix["human_required"] == []
    assert matrix["known"] == [{"question": "How did you hear about us?", "question_key": "how_did_you_hear", "source": "profile"}]


def test_disabled_placeholder_or_ambiguous_native_options_stay_blocked():
    cases = [
        '<option disabled value="s">Social Media</option>',
        '<optgroup disabled><option value="s">Social Media</option></optgroup>',
        '<option value="">Social Media</option>', '<option>Social Media</option>',
        '<option value="s">Social Media</option><option value="t">Social Media</option>',
        '<option value="s">Social Media</option><option value="s">Other</option>',
    ]
    for options in cases:
        matrix = _matrix_for_select('<select id="source" required>' + options + '</select>')
        assert matrix["known"] == []
        assert len(matrix["human_required"]) == 1


def test_multiple_disabled_or_duplicate_native_controls_do_not_get_known_answer():
    for control in [
        '<select id="source" required multiple><option value="s">Social Media</option></select>',
        '<select id="source" required disabled><option value="s">Social Media</option></select>',
        '<select id="source" name="dup" required><option value="s">Social Media</option></select><select name="dup"></select>',
    ]:
        matrix = _matrix_for_select(control)
        assert matrix["known"] == []
        assert len(matrix["human_required"]) == 1


def test_missing_select_schema_is_not_a_free_text_fallback():
    payload = {"fields": [{"name": "source", "label": "How did you hear about us?", "type": "select", "required": True}]}
    for groups in [None, [], "malformed", [False]]:
        questions = _questions_from_fields({**payload, "select_groups": groups})
        matrix = build_coverage_matrix(profile={"screening_defaults": {"how_did_you_hear": "Social Media"}}, questions=questions)
        assert matrix["known"] == []
        assert matrix["human_required"][0]["reason"] == "native_option_inventory_unavailable"


def test_read_only_prepare_does_not_claim_review_ready_for_unavailable_option():
    from prepare_live_job import prepare_live_job, _dispatch_live_html
    html = '''<h1>Software Engineer Intern</h1><label for="source">How did you hear about us?</label>
        <select id="source" required><option value="other">Other</option></select>'''
    url = "https://jobs.lever.co/example/123/apply"
    identity = {"company": "Example", "role": "Software Engineer Intern", "requisition": "123"}
    class SyntheticReadOnlyPage:
        target_id = "synthetic"

        def read_only_snapshot(self):
            return {"read_only": True, "target_id": "synthetic", "url": url, "html": html}
    result = prepare_live_job(page=SyntheticReadOnlyPage(), target_id="synthetic", expected_url=url,
        expected_identity=identity, profile={"screening_defaults": {"how_did_you_hear": "Social Media"}},
        prepare=lambda **kwargs: _dispatch_live_html(**kwargs, expected_identity=identity),
        coverage=build_coverage_matrix)
    assert result["review_ready"] is False
    assert result["submission_enabled"] is False
    assert result["applied_answers"]["field_evidence"] == []


def test_missing_other_option_value_cannot_hide_a_duplicate_runtime_value():
    matrix = _matrix_for_select('<select id="source" required><option value="social">Social Media</option><option>social</option></select>')
    assert matrix["known"] == []
    assert len(matrix["human_required"]) == 1


def test_optional_unavailable_select_is_skipped_without_known_answer():
    matrix = _matrix_for_select('<select id="source"><option value="other">Other</option></select>')
    assert matrix["known"] == []
    assert matrix["human_required"] == []
    assert len(matrix["optional_skip"]) == 1
