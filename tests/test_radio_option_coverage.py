"""Synthetic Lever radio structure reduced from actual public SWE pilots."""
from answer_coverage import build_coverage_matrix
from prepare_job import prepare_saved_html
from prepare_live_job import _questions_from_fields

URL = 'https://jobs.lever.co/example/123/apply'
QUESTION = 'Are you legally authorized to work in the United States?'
PROFILE = {'work_authorization': True}


def inspect_radios(options):
    html = '<li class="application-question"><div class="application-label">' + QUESTION + '</div>' + options + '</li>'
    return prepare_saved_html(html_text=html, page_url=URL)


def test_radio_preparation_emits_one_option_checked_question():
    payload = inspect_radios('''<label><input type="radio" name="auth" value="yes" required>Yes</label>
      <label><input type="radio" name="auth" value="no">No</label>''')
    questions = _questions_from_fields(payload)
    assert len(questions) == 1
    assert questions[0]['native_radio']['options'] == [
        {'label':'Yes', 'value':'yes', 'disabled':False},
        {'label':'No', 'value':'no', 'disabled':False}]
    matrix = build_coverage_matrix(profile=PROFILE, questions=questions)
    assert matrix['human_required'] == []
    assert matrix['known'] == [{'question':QUESTION, 'question_key':'work_authorization', 'source':'profile'}]
    assert payload['submission_enabled'] is False


def test_known_fact_absent_from_radio_options_cannot_pass_preparation():
    payload = inspect_radios('<label><input type="radio" name="auth" value="no" required>No</label>')
    matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(payload))
    assert matrix['known'] == []
    assert matrix['human_required'][0]['reason'] == 'answer_not_in_native_options'


def test_unusable_radio_definitions_never_become_known_answers():
    cases = [
        '<label><input type="radio" name="auth" value="yes" required disabled>Yes</label>',
        '<fieldset disabled><label><input type="radio" name="auth" value="yes" required>Yes</label></fieldset>',
        '<label><input type="radio" name="auth" value="" required>Yes</label>',
        '<label><input type="radio" name="auth" required>Yes</label>',
        '<label><input type="radio" name="auth" value="a" required>Yes</label><label><input type="radio" name="auth" value="b">Yes</label>',
        '<label><input type="radio" name="auth" value="a" required>Yes</label><label><input type="radio" name="auth" value="a">No</label>',
        '<label><input type="radio" name="auth" value="a" required>Yes</label><label><input type="radio" name="auth">a</label>',
    ]
    for options in cases:
        matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(inspect_radios(options)))
        assert matrix['known'] == []
        assert len(matrix['human_required']) == 1


def test_radio_name_collisions_preserve_required_blockers_instead_of_merging():
    base = '<li class="application-question"><div class="application-label">' + QUESTION + '</div><label><input type="radio" name="auth" value="yes" required>Yes</label></li>'
    for extra in [base, '<input type="text" name="auth">',
                  '<li class="application-question"><div class="application-label">Other question</div><label><input type="radio" name="auth" value="no">No</label></li>',
                  '<input type="checkbox" name="auth" value="other">']:
        payload = prepare_saved_html(html_text=base + extra, page_url=URL)
        matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(payload))
        assert matrix['known'] == []
        assert matrix['human_required'][0]['reason'] == 'native_option_inventory_unavailable'


def test_missing_partial_malformed_radio_schema_is_not_free_text():
    from copy import deepcopy
    payload = inspect_radios('<label><input type="radio" name="auth" value="yes" required>Yes</label>')
    for groups in [None, [], 'bad', [False], [{**payload['choice_groups'][0], 'options':[]}]]:
        changed = {**payload, 'choice_groups':groups}
        matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(changed))
        assert matrix['known'] == []
        assert matrix['human_required'][0]['reason'] == 'native_option_inventory_unavailable'
    changed = deepcopy(payload)
    del changed['choice_groups'][0]['options'][0]['disabled']
    matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(changed))
    assert matrix['known'] == []


def test_unknown_radio_fact_is_not_inferred_from_required_yes_no():
    payload = inspect_radios('<label><input type="radio" name="auth" value="yes" required>Yes</label><label><input type="radio" name="auth" value="no">No</label>')
    matrix = build_coverage_matrix(profile={}, questions=_questions_from_fields(payload))
    assert matrix['known'] == []
    assert matrix['human_required'][0]['reason'] == 'unknown_profile_fact'


def test_optional_unavailable_radio_is_skipped_once():
    payload = inspect_radios('<label><input type="radio" name="auth" value="no">No</label><label><input type="radio" name="auth" value="unknown">Unknown</label>')
    matrix = build_coverage_matrix(profile=PROFILE, questions=_questions_from_fields(payload))
    assert matrix['known'] == []
    assert matrix['human_required'] == []
    assert len(matrix['optional_skip']) == 1


def test_read_only_preparation_with_unavailable_radio_cannot_claim_review_ready():
    from prepare_live_job import prepare_live_job, _dispatch_live_html
    html = '<h1>Software Engineer Intern</h1><li class="application-question"><div class="application-label">' + QUESTION + '</div><label><input type="radio" name="auth" value="no" required>No</label></li>'
    identity = {'company':'Example','role':'Software Engineer Intern','requisition':'123'}
    class SyntheticReadOnlyPage:
        target_id = 'synthetic'
        def read_only_snapshot(self):
            return {'read_only':True,'target_id':'synthetic','url':URL,'html':html}
    result = prepare_live_job(page=SyntheticReadOnlyPage(), target_id='synthetic', expected_url=URL,
        expected_identity=identity, profile=PROFILE,
        prepare=lambda **kwargs: _dispatch_live_html(**kwargs, expected_identity=identity),
        coverage=build_coverage_matrix)
    assert result['review_ready'] is False
    assert result['submission_enabled'] is False
    assert result['applied_answers']['field_evidence'] == []
