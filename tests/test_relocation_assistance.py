"""Offline synthetic relocation facts; never infer assistance from willingness."""
import pytest

from canonical_answers import (
    CanonicalAnswerError,
    canonical_review_fields,
    resolve_fact,
    verify_profile_answers,
)
from question_engine import QuestionAnswerEngine


REQUIRES = 'requires_relocation_assistance'
CAN_RELOCATE = 'can_relocate_without_assistance'
QUESTIONS = [
    ('Do you require relocation assistance?', REQUIRES),
    ('Can you relocate without assistance?', CAN_RELOCATE),
    ('Can you relocate at your own expense?', CAN_RELOCATE),
]
COMMUTE_QUESTION = 'Are you able to commute to the location listed on the requisition without relocation assistance?'


@pytest.mark.parametrize('section', ['screening_defaults', 'application_facts'])
@pytest.mark.parametrize('stored_field', [REQUIRES, CAN_RELOCATE])
@pytest.mark.parametrize('assistance_value', [False, True])
@pytest.mark.parametrize('willing', [True, False, None])
def test_generic_relocation_facts_do_not_establish_location_specific_commute(
    section, stored_field, assistance_value, willing
):
    profile = {section: {'willing_to_relocate': willing, stored_field: assistance_value}}
    result = QuestionAnswerEngine(profile=profile).answer(COMMUTE_QUESTION, company='Fixture Employer')
    assert (result.status, result.question_key, result.reason) == ('unknown', 'unknown', 'unknown_question')
    assert result.answer is None
    assert result.source is None
    with pytest.raises(CanonicalAnswerError, match='missing'):
        canonical_review_fields(profile, {result.question_key: {'selector': '#commute'}})


@pytest.mark.parametrize(('question', 'field'), QUESTIONS)
@pytest.mark.parametrize('requires_assistance', [False, True])
def test_explicit_assistance_facts_have_correct_question_and_review_polarity(
    question, field, requires_assistance
):
    profile = {'screening_defaults': {
        'willing_to_relocate': True,
        REQUIRES: requires_assistance,
        CAN_RELOCATE: not requires_assistance,
    }}
    expected = 'Yes' if (requires_assistance if field == REQUIRES else not requires_assistance) else 'No'
    result = QuestionAnswerEngine(profile=profile).answer(question, company='Fixture Employer')
    assert result.status == 'answered'
    assert result.question_key == field
    assert result.answer == expected
    assert result.source == 'profile'
    # Review derives the same fact independently, not from the engine result.
    controls = {field: {'selector': '#assistance', 'operation': 'native_select'}}
    assert canonical_review_fields(profile, controls) == {'#assistance': expected}
    verify_profile_answers(profile, {field: expected})
    with pytest.raises(CanonicalAnswerError, match='conflicting'):
        verify_profile_answers(profile, {field: 'No' if expected == 'Yes' else 'Yes'})

    from review_reconciler import reconcile_review
    from test_review_safety import inputs
    args = inputs()
    args.update(profile_fields=canonical_review_fields(profile, controls),
                required_parser_repairs=[], required_question_ids=['relocation'],
                question_fields={'relocation': '#assistance'})
    args['preparation_evidence']['applied_answers']['field_evidence'] = []
    args['server_review'].update(fields={'#assistance': expected}, questions=[{
        'id': 'relocation', 'required': True, 'answered': True, 'verified': True, 'answer': expected,
    }])
    assert reconcile_review(**args)['review_authoritative'] is True
    wrong = 'No' if expected == 'Yes' else 'Yes'
    args['server_review']['fields']['#assistance'] = wrong
    args['server_review']['questions'][0]['answer'] = wrong
    assert reconcile_review(**args)['review_authoritative'] is False


@pytest.mark.parametrize('section', ['screening_defaults', 'application_facts'])
@pytest.mark.parametrize('stored_field', [REQUIRES, CAN_RELOCATE])
@pytest.mark.parametrize(('value', 'normalized'), [(True, 'Yes'), (False, 'No'), ('Yes', 'Yes'), ('No', 'No')])
def test_each_explicit_alias_resolves_both_polarities(section, stored_field, value, normalized):
    profile = {section: {stored_field: value}}
    for question, field in QUESTIONS:
        expected = normalized if field == stored_field else ('No' if normalized == 'Yes' else 'Yes')
        assert resolve_fact(profile, field) == expected
        result = QuestionAnswerEngine(profile=profile).answer(question)
        assert result.status == 'answered'
        assert result.answer == expected
        assert result.question_key == field
        assert canonical_review_fields(profile, {
            field: {'selector': '#assistance', 'operation': 'native_select'},
        }) == {'#assistance': expected}


@pytest.mark.parametrize('section', ['screening_defaults', 'application_facts'])
@pytest.mark.parametrize('stored_field', [REQUIRES, CAN_RELOCATE])
@pytest.mark.parametrize('malformed', [False, True])
def test_all_aliases_are_checked_for_conflicts_and_malformed_facts(section, stored_field, malformed):
    profile = {
        'screening_defaults': {REQUIRES: False, CAN_RELOCATE: True},
        'application_facts': {REQUIRES: 'No', CAN_RELOCATE: 'Yes'},
    }
    profile[section][stored_field] = 'maybe' if malformed else stored_field == REQUIRES
    for question, field in QUESTIONS:
        with pytest.raises(CanonicalAnswerError, match='malformed' if malformed else 'conflicting'):
            resolve_fact(profile, field)
        result = QuestionAnswerEngine(profile=profile).answer(question)
        assert result.status == 'conflict'
        assert result.reason == 'conflicting_profile_fact'
        assert result.answer is None
        with pytest.raises(CanonicalAnswerError):
            canonical_review_fields(profile, {
                field: {'selector': '#assistance', 'operation': 'native_select'},
            })


@pytest.mark.parametrize('same_value', [False, True])
def test_opposite_facts_cannot_both_have_the_same_truth_value(same_value):
    profile = {'screening_defaults': {REQUIRES: same_value, CAN_RELOCATE: same_value}}
    for question, field in QUESTIONS:
        result = QuestionAnswerEngine(profile=profile).answer(question)
        assert result.status == 'conflict'
        assert result.answer is None
        with pytest.raises(CanonicalAnswerError, match='conflicting'):
            resolve_fact(profile, field)


@pytest.mark.parametrize(('question', 'field'), [
    ('Do you need relocation assistance?', REQUIRES),
    ('Will you require relocation assistance?', REQUIRES),
    ('Would you need any relocation assistance for this role?', REQUIRES),
    ('Is relocation assistance required?', REQUIRES),
    ('Is relocation assistance needed?', REQUIRES),
    ('Do you require relocation assistance from the employer?', REQUIRES),
    ('Are you able to relocate without relocation assistance?', CAN_RELOCATE),
    ('Can you relocate without any assistance for this position?', CAN_RELOCATE),
    ('Will you be able to relocate without any relocation assistance?', CAN_RELOCATE),
    ('Can you relocate at your own expense?', CAN_RELOCATE),
    ('  DO YOU\n NEED ANY RELOCATION ASSISTANCE?*  ', REQUIRES),
])
@pytest.mark.parametrize('requires_assistance', [False, True])
def test_equivalent_assistance_prompts_preserve_polarity(question, field, requires_assistance):
    profile = {'screening_defaults': {REQUIRES: requires_assistance, CAN_RELOCATE: not requires_assistance}}
    result = QuestionAnswerEngine(profile=profile).answer(question)
    assert result.status == 'answered'
    assert result.question_key == field
    assert result.answer == ('Yes' if (requires_assistance if field == REQUIRES else not requires_assistance) else 'No')


@pytest.mark.parametrize('profile', [
    {},
    {'screening_defaults': {'willing_to_relocate': True}},
    {'screening_defaults': {'willing_to_relocate': False}},
    {'application_facts': {'willing_to_relocate': True}},
    {'screening_defaults': {REQUIRES: None, CAN_RELOCATE: None}},
    {'application_facts': {REQUIRES: None, CAN_RELOCATE: None}},
])
def test_unknown_assistance_facts_stay_unknown_even_with_willingness_or_historical_answers(profile):
    engine = QuestionAnswerEngine(profile=profile, google_doc_answers=[
        {'question_key': REQUIRES, 'answer': 'No'},
        {'question_key': CAN_RELOCATE, 'answer': 'Yes'},
    ])
    for question, field in QUESTIONS:
        result = engine.answer(question)
        assert result.status == 'unknown'
        assert result.reason == 'unknown_profile_fact'
        assert result.question_key == field
        assert result.answer is None
        with pytest.raises(CanonicalAnswerError, match='missing'):
            canonical_review_fields(profile, {
                field: {'selector': '#assistance', 'operation': 'native_select'},
            })


@pytest.mark.parametrize('question', [
    'Do you currently live near the location listed on the requisition?',
    'Are you currently able to commute to the location listed on the requisition without relocation assistance?',
    'Are you able to commute to the location listed on the requisition without relocating?',
    'Can you commute to the office from your current residence?',
    'Do you require visa sponsorship or relocation assistance?',
    'Do you require relocation assistance or visa sponsorship?',
    'Do you require relocation assistance? Explain why.',
    'Do you not require relocation assistance?',
    'Can you relocate without assistance and work in Canada?',
    'Are you willing to relocate without relocation assistance?',
    'Will you require housing or transportation assistance?',
])
def test_local_residence_and_materially_different_questions_are_not_inferred(question):
    profile = {'screening_defaults': {'willing_to_relocate': True, REQUIRES: False, CAN_RELOCATE: True}}
    result = QuestionAnswerEngine(profile=profile).answer(question)
    assert result.status == 'unknown'
    assert result.question_key == 'unknown'
    assert result.answer is None


@pytest.mark.parametrize('stored_field', [REQUIRES, CAN_RELOCATE])
@pytest.mark.parametrize('value', ['', 'unknown', 'false', 'yes', 0, 1, [], {}])
def test_invalid_assistance_values_never_become_boolean_answers(stored_field, value):
    profile = {'screening_defaults': {stored_field: value}}
    engine = QuestionAnswerEngine(profile=profile)
    for question, field in QUESTIONS:
        result = engine.answer(question)
        assert result.status == 'conflict'
        assert result.answer is None
        with pytest.raises(CanonicalAnswerError, match='malformed'):
            resolve_fact(profile, field)


def test_self_funded_relocation_does_not_change_current_address_or_infer_willingness():
    import copy
    profile = {
        'contact': {'location': {'city': 'Fixture Origin'}},
        'screening_defaults': {REQUIRES: False, CAN_RELOCATE: True},
    }
    original = copy.deepcopy(profile)
    engine = QuestionAnswerEngine(profile=profile)
    assert engine.answer(QUESTIONS[2][0]).answer == 'Yes'
    assert engine.answer('Are you willing to relocate?').status == 'unknown'
    assert resolve_fact(profile, 'city') == 'Fixture Origin'
    assert profile == original
