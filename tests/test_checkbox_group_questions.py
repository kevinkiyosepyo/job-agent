"""Synthetic reduced checkbox schema; not employer data or selected answers."""
from copy import deepcopy
import pytest

from answer_coverage import build_coverage_matrix
from prepare_live_job import _questions_from_fields


def test_known_checkbox_fact_does_not_prove_a_supported_selection():
    payload = {'fields': [{'label': 'How did you hear about this role?',
                          'name': 'source', 'type': 'checkbox', 'required': True}]}
    questions = _questions_from_fields(payload)
    matrix = build_coverage_matrix(
        profile={'screening_defaults': {'how_did_you_hear': 'Social Media'}}, questions=questions)
    assert matrix['known'] == []
    assert questions[0]['type'] == 'checkbox'
    assert matrix['human_required'][0]['reason'] == 'checkbox_selection_unverified'


def checkbox_payload():
    return {
        'fields': [
            {'label': 'Synthetic Alpha', 'name': 'majors[]', 'type': 'checkbox', 'required': True},
            {'label': 'Synthetic Beta', 'name': 'majors[]', 'type': 'checkbox', 'required': True},
        ],
        'choice_groups': [{
            'name': 'majors[]', 'label': 'Undergrad Discipline(s)', 'type': 'checkbox',
            'required': True, 'source': 'static_html', 'bound_values_verified': False,
            'options': [{'id': 'synthetic-a', 'label': 'Synthetic Alpha', 'value': ' a '},
                        {'id': 'synthetic-b', 'label': 'Synthetic Beta', 'value': 'b'}],
        }],
    }


def test_group_prompt_replaces_option_questions_without_changing_inventory():
    payload = checkbox_payload()
    before = deepcopy(payload)
    assert _questions_from_fields(payload) == [{
        'label': 'Undergrad Discipline(s)', 'required': True, 'type': 'checkbox',
        'native_checkbox': payload['choice_groups'][0],
    }]
    assert payload == before


@pytest.mark.parametrize('mutate', [
    lambda p: p['choice_groups'].append(deepcopy(p['choice_groups'][0])),
    lambda p: p['choice_groups'][0].update(source='unverified'),
    lambda p: p['choice_groups'][0].update(bound_values_verified=True),
    lambda p: p['choice_groups'][0].update(label=' '),
    lambda p: p['choice_groups'][0].update(required='true'),
    lambda p: p['choice_groups'][0].update(options=None),
    lambda p: p['choice_groups'][0]['options'].pop(),
    lambda p: p['choice_groups'][0]['options'][0].update(label='Synthetic mismatch'),
    lambda p: p['choice_groups'][0]['options'].__setitem__(0, None),
    lambda p: p['fields'][1].update(type='text'),
])
def test_ambiguous_or_incomplete_group_keeps_original_questions(mutate):
    payload = checkbox_payload()
    mutate(payload)
    questions = _questions_from_fields(payload)
    assert [q['label'] for q in questions] == ['Synthetic Alpha', 'Synthetic Beta']
    assert all(q.get('native_checkbox') is None for q in questions)


@pytest.mark.parametrize('field_required,group_required', [(False, True), (True, False)])
def test_requirement_is_not_weakened_by_collapsing_the_group(field_required, group_required):
    payload = checkbox_payload()
    for field in payload['fields']:
        field['required'] = field_required
    payload['choice_groups'][0]['required'] = group_required
    assert _questions_from_fields(payload)[0]['required'] is True


def test_optional_unknown_group_is_one_skip_without_a_guessed_answer():
    payload = checkbox_payload()
    for field in payload['fields']:
        field['required'] = False
    payload['choice_groups'][0]['required'] = False
    matrix = build_coverage_matrix(profile={}, questions=_questions_from_fields(payload))
    assert matrix['known'] == [] and matrix['human_required'] == []
    assert len(matrix['optional_skip']) == 1


def test_unrelated_text_question_is_preserved_next_to_a_group():
    payload = checkbox_payload()
    payload['fields'].insert(1, {'name': 'other', 'label': 'Other question', 'type': 'text', 'required': False})
    questions = _questions_from_fields(payload)
    assert len(questions) == 2
    assert questions[1] == {'label': 'Other question', 'required': False}
    assert questions[0]['native_checkbox']['options'][0]['value'] == ' a '


def test_synthetic_read_only_html_group_does_not_make_review_ready():
    from prepare_live_job import _dispatch_live_html, prepare_live_job
    url = 'https://job-boards.greenhouse.io/example/jobs/123'
    identity = {'company': 'Example', 'role': 'Software Engineer Intern', 'requisition': '123'}
    html = '''<title>Job Application for Software Engineer Intern at Example</title>
    <h1>Software Engineer Intern</h1>
    <fieldset id="synthetic_source" aria-required="true">
      <legend>How did you hear about this role?</legend>
      <input type="checkbox" name="source[]" id="a" value="social"><label for="a">Social Media</label>
      <input type="checkbox" name="source[]" id="b" value="other"><label for="b">Other</label>
    </fieldset>'''
    class SyntheticReadOnlyPage:
        target_id = 'synthetic'
        def read_only_snapshot(self):
            return {'read_only': True, 'target_id': self.target_id, 'url': url, 'html': html}
    result = prepare_live_job(
        page=SyntheticReadOnlyPage(), target_id='synthetic', expected_url=url,
        expected_identity=identity, profile={'screening_defaults': {'how_did_you_hear': 'Social Media'}},
        prepare=lambda **kwargs: _dispatch_live_html(**kwargs, expected_identity=identity),
        coverage=build_coverage_matrix)
    assert result['review_ready'] is False
    assert result['answer_coverage']['known'] == []
    assert len(result['answer_coverage']['human_required']) == 1
    assert result['answer_coverage']['human_required'][0]['reason'] == 'checkbox_selection_unverified'
    assert result['submission_enabled'] is False
    assert result['applied_answers']['field_evidence'] == []
