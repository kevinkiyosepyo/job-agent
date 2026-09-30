"""Synthetic onboarding facts must reach real application answer resolution."""
import pytest
from canonical_answers import CanonicalAnswerError, resolve_fact
from question_engine import QuestionAnswerEngine


@pytest.mark.parametrize(('question', 'field', 'value', 'expected'), [
    ('Do you have any company affiliations?', 'has_company_affiliations', False, 'No'),
    ('Do you need OPT (Optional Practical Training)?', 'needs_opt', True, 'Yes'),
    ('Do you need CPT (Curricular Practical Training)?', 'needs_cpt', False, 'No'),
    ('Do you need employer sponsorship now?', 'sponsorship_now', False, 'No'),
    ('Will you need employer sponsorship in the future?', 'sponsorship_future', True, 'Yes'),
    ('Are you subject to a restrictive covenant (such as a non-compete)?', 'restrictive_covenant', False, 'No'),
    ('Are you a US citizen?', 'us_citizen', True, 'Yes'),
    ('Are you a U.S. citizen?', 'us_citizen', False, 'No'),
    ('Do you need OPT?', 'needs_opt', True, 'Yes'),
    ('Do you require Optional Practical Training (OPT)?', 'needs_opt', False, 'No'),
    ('Do you need CPT?', 'needs_cpt', True, 'Yes'),
    ('Do you require Curricular Practical Training (CPT)?', 'needs_cpt', False, 'No'),
    ('Do you have any affiliations to any companies?', 'has_company_affiliations', True, 'Yes'),
    ('Are you subject to a restrictive covenant?', 'restrictive_covenant', False, 'No'),
    ('What is your earliest available start date?', 'available_start_date', '2027-06-01', '2027-06-01'),
    ('When can you start full-time after graduation?', 'full_time_start_date', '2028-06-01', '2028-06-01'),
])
def test_saved_screening_facts_are_reused(question, field, value, expected):
    profile = {'application_facts': {field: value}}
    result = QuestionAnswerEngine(profile=profile).answer(question)
    assert (result.status, result.answer, result.source) == ('answered', expected, 'profile')
    assert resolve_fact(profile, field) == expected


@pytest.mark.parametrize('question', [
    'Are you a US citizen?', 'Do you need OPT?', 'Do you need CPT?',
    'Do you have any affiliations to any companies?',
])
def test_unknown_eligibility_is_not_inferred(question):
    engine = QuestionAnswerEngine(profile={'work_authorization': True, 'requires_sponsorship': False})
    assert engine.answer(question).status == 'unknown'


@pytest.mark.parametrize('field', ['us_citizen', 'needs_opt', 'needs_cpt', 'has_company_affiliations', 'restrictive_covenant'])
def test_malformed_sensitive_boolean_fails_closed(field):
    with pytest.raises(CanonicalAnswerError):
        resolve_fact({'application_facts': {field: 'maybe'}}, field)


@pytest.mark.parametrize(('question', 'expected'), [
    ('Are you currently employed by this company?', 'No'),
    ('Have you previously been employed by this company?', 'Yes'),
    ('Do you have relatives employed by this company?', 'No'),
    ('Have you ever worked for Example Corp?', 'Yes'),
    ('Are you currently employed by Example Corp?', 'No'),
])
def test_company_disclosures_are_reused_only_for_exact_company(question, expected):
    profile = {'company_disclosures': [{'company': 'Example Corp', 'current_employee': False,
        'former_employee': True, 'relatives_employed': False}]}
    engine = QuestionAnswerEngine(profile=profile)
    answer = engine.answer(question, company='  EXAMPLE   CORP ')
    assert (answer.status, answer.answer, answer.source) == ('answered', expected, 'profile:company')
    assert engine.answer(question, company='Another Corp').status == 'unknown'
    assert engine.answer(question).status == 'unknown'


@pytest.mark.parametrize(('question', 'company', 'expected'), [
    ('Were you formerly employed by Example Corp?', 'Example Corp', 'Yes'),
    ('Were you formerly employed by Example Corp?', '  EXAMPLE   CORP ', 'Yes'),
    ('Were you formerly employed by this company?', 'Example Corp', 'Yes'),
    ('Were you formerly employed by Another Corp?', 'Another Corp', 'No'),
    ('Were you formerly employed by Example Corp?', 'Another Corp', None),
    ('Were you formerly employed by Another Corp?', 'Example Corp', None),
    ('Were you formerly employed by Example Corp?', None, None),
    ('Were you formerly employed by Example Corp Subsidiary?', 'Example Corp', None),
    ('Were you formerly employed by Example Corp in the past year?', 'Example Corp', None),
])
def test_wizard_formerly_employed_wording_requires_exact_company(question, company, expected):
    engine = QuestionAnswerEngine(profile={'company_disclosures': [
        {'company': 'Example Corp', 'former_employee': True},
        {'company': 'Another Corp', 'former_employee': False},
    ]})
    answer = engine.answer(question, company=company)
    assert (answer.status, answer.answer) == ('unknown' if expected is None else 'answered', expected)
    if expected is not None:
        assert (answer.source, answer.question_key) == ('profile:company', 'former_employee')


@pytest.mark.parametrize('records', [
    [], [{'company': 'Another Corp', 'former_employee': False}],
    [{'company': 'Example Corp', 'former_employee': None}],
])
def test_global_affiliation_no_does_not_answer_employer_specific_history(records):
    engine = QuestionAnswerEngine(profile={'application_facts': {'has_company_affiliations': False},
        'company_disclosures': records})
    result = engine.answer('Have you previously been employed by this company?', company='Example Corp')
    assert result.status == 'unknown'


@pytest.mark.parametrize('records', [
    [{'company': 'Example Corp', 'current_employee': 'maybe'}],
    [{'company': 'Example Corp', 'current_employee': False},
     {'company': 'example corp', 'current_employee': True}],
    {'company': 'Example Corp', 'current_employee': False},
])
def test_malformed_or_duplicate_company_records_fail_closed(records):
    result = QuestionAnswerEngine(profile={'company_disclosures': records}).answer(
        'Are you currently employed by this company?', company='Example Corp')
    assert result.status == 'conflict'
    assert result.answer is None


def test_ever_employed_requires_both_timeframes():
    result = QuestionAnswerEngine(profile={'company_disclosures': [
        {'company': 'Example Corp', 'former_employee': False}]}).answer(
            'Have you ever worked for Example Corp?', company='Example Corp')
    assert result.status == 'unknown'


def test_citizenship_answer_feeds_posting_eligibility_without_conflicting_legacy_fact():
    from posting_qualifications import qualification_decision
    posting = {'content': 'U.S. citizenship required'}
    assert qualification_decision(posting, {'application_facts': {'us_citizen': True}})['status'] == 'qualified'
    assert qualification_decision(posting, {'application_facts': {'us_citizen': False}})['status'] != 'qualified'
    assert qualification_decision(posting, {'citizenship': 'United States'})['status'] == 'qualified'
    conflicting = {'citizenship': 'United States', 'application_facts': {'us_citizen': False}}
    assert qualification_decision(posting, conflicting)['status'] != 'qualified'
    assert QuestionAnswerEngine(profile=conflicting).answer('Are you a US citizen?').status == 'conflict'


def test_company_coverage_uses_scoped_bucket_and_keeps_values_private():
    from answer_coverage import build_coverage_matrix
    matrix = build_coverage_matrix(profile={'company_disclosures': [
        {'company': 'Example Corp', 'former_employee': True}]}, company='Example Corp',
        questions=[{'label': 'Have you previously been employed by this company?', 'required': True}])
    assert len(matrix['company_specific']) == 1
    assert matrix['human_required'] == []
    assert 'answer' not in matrix['company_specific'][0]


@pytest.mark.parametrize('field', ['sponsorship', 'requires_sponsorship'])
def test_legacy_extension_alias_without_split_fields_still_resolves(field):
    assert resolve_fact({'application_facts': {field: False}}, field) == 'No'


@pytest.mark.parametrize('field', ['sponsorship', 'requires_sponsorship'])
def test_existing_semantic_aliases_resolve_new_split_sponsorship(field):
    assert resolve_fact({'application_facts': {'sponsorship_now': False, 'sponsorship_future': True}}, field) == 'No'


def test_learned_review_accepts_boolean_split_sponsorship_from_onboarding():
    import schonfeld_form
    schonfeld_form.verify_profile_answers(
        {'application_facts': {'sponsorship_now': False, 'sponsorship_future': True}},
        {'sponsorship_now': {'exact_option': 'No'}, 'sponsorship_future': {'exact_option': 'Yes'}})


def test_split_sponsorship_does_not_conflate_opt_or_timeframes():
    engine = QuestionAnswerEngine(profile={'application_facts': {
        'sponsorship_now': False, 'sponsorship_future': True, 'needs_opt': True}})
    assert engine.answer('Do you require visa sponsorship?').answer == 'No'
    assert engine.answer('Will you require sponsorship?').answer == 'Yes'
    assert engine.answer('Will you now or in the future require sponsorship?').answer == 'Yes'
    assert engine.answer('Do you need OPT?').answer == 'Yes'


@pytest.mark.parametrize('question', [
    'Are you a US citizen or permanent resident?',
    'Are you currently on OPT?', 'Are you eligible for STEM OPT?',
    'Do you need CPT or OPT?', 'Are you legally authorized to work in Canada?',
    'Are you subject to a restrictive covenant with Example Corp?',
])
def test_related_but_different_legal_questions_are_not_guessed(question):
    engine = QuestionAnswerEngine(profile={'application_facts': {
        'us_citizen': True, 'needs_opt': False, 'needs_cpt': False, 'restrictive_covenant': False}})
    assert engine.answer(question).status == 'unknown'
