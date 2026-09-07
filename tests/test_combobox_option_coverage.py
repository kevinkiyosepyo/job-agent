"""Synthetic reduced modern Greenhouse combobox; not employer or live evidence."""
from answer_coverage import build_coverage_matrix
from prepare_live_job import _dispatch_live_html, prepare_live_job


def test_unverified_combobox_cannot_make_read_only_preparation_review_ready():
    url = 'https://job-boards.greenhouse.io/example/jobs/123'
    identity = {'company':'Example','role':'Software Engineer Intern','requisition':'123'}
    html = '''<title>Job Application for Software Engineer Intern at Example</title>
      <h1>Software Engineer Intern</h1>
      <label for="source">How did you hear about this role?</label>
      <input id="source" role="combobox" aria-required="true" aria-expanded="false">'''
    class SyntheticReadOnlyPage:
        target_id = 'synthetic'
        def read_only_snapshot(self):
            return {'read_only':True,'target_id':'synthetic','url':url,'html':html}
    result = prepare_live_job(page=SyntheticReadOnlyPage(), target_id='synthetic', expected_url=url,
        expected_identity=identity, profile={'screening_defaults':{'how_did_you_hear':'Social Media'}},
        prepare=lambda **kwargs: _dispatch_live_html(**kwargs, expected_identity=identity),
        coverage=build_coverage_matrix)
    assert result['review_ready'] is False
    assert result['answer_coverage']['known'] == []
    assert result['answer_coverage']['human_required'][0]['reason'] == 'combobox_options_unverified'
    assert result['submission_enabled'] is False
    assert result['applied_answers']['field_evidence'] == []


def test_optional_combobox_is_skipped_without_a_known_option():
    matrix = build_coverage_matrix(
        profile={'screening_defaults':{'how_did_you_hear':'Social Media'}},
        questions=[{'label':'How did you hear about this role?', 'type':'combobox', 'required':False}])
    assert matrix['known'] == []
    assert matrix['human_required'] == []
    assert len(matrix['optional_skip']) == 1


def test_combobox_cannot_borrow_native_or_claimed_bound_evidence():
    for extra in [
        {'options':[{'label':'Social Media','value':'social'}]},
        {'native_select':{'source':'static_html','multiple':False,'disabled':False,
                          'options':[{'label':'Social Media','value':'social','disabled':False}]}},
        {'native_radio':{'source':'static_html','type':'radio',
                         'options':[{'label':'Social Media','value':'social','disabled':False}]}},
        {'source':'live_client_bound_form','bound_values_verified':True},
    ]:
        matrix = build_coverage_matrix(
            profile={'screening_defaults':{'how_did_you_hear':'Social Media'}},
            questions=[{'label':'How did you hear about this role?', 'type':'combobox', 'required':True, **extra}])
        assert matrix['known'] == []
        assert matrix['human_required'][0]['reason'] == 'combobox_options_unverified'


def test_unknown_combobox_fact_keeps_original_fact_blocker():
    matrix = build_coverage_matrix(profile={}, questions=[{
        'label':'Are you legally authorized to work in the United States?',
        'type':'combobox', 'required':True}])
    assert matrix['known'] == []
    assert matrix['human_required'][0]['reason'] == 'unknown_profile_fact'


def test_non_combobox_question_conversion_is_unchanged():
    from prepare_live_job import _questions_from_fields
    fields = [{'label':'How did you hear about this role?', 'name':'source',
               'type':'text', 'required':True}]
    questions = _questions_from_fields({'fields':fields})
    assert questions == [{'label':'How did you hear about this role?', 'required':True}]
    matrix = build_coverage_matrix(
        profile={'screening_defaults':{'how_did_you_hear':'Social Media'}},questions=questions)
    assert matrix['human_required'] == []
    assert len(matrix['known']) == 1


def test_combobox_conversion_preserves_type_without_mutating_raw_inventory():
    from copy import deepcopy
    from prepare_live_job import _questions_from_fields
    payload = {'fields':[{'label':'How did you hear about this role?', 'name':'source',
                           'type':'combobox','required':True}]}
    before = deepcopy(payload)
    assert _questions_from_fields(payload) == [{
        'label':'How did you hear about this role?', 'required':True, 'type':'combobox'}]
    assert payload == before
