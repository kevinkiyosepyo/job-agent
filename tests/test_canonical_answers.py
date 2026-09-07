"""Schema-grounded synthetic facts, no external access or candidate secrets."""
import importlib.util
import copy

import pytest


def canonical():
    assert importlib.util.find_spec('canonical_answers'), 'reusable canonical fact resolver missing'
    import canonical_answers
    return canonical_answers


def profile():
    return {
        'name': {'first': 'Fixture', 'last': 'Person', 'full': 'Fixture Person'},
        'contact': {'email': 'fixture@example.test', 'phone': '(555) 010-1234',
                    'location': {'city': 'Fairfax', 'state': 'VA', 'country': 'United States', 'zip': '22032'}},
        'education': {'university': 'University of California, San Diego', 'degree': 'Bachelor of Science',
                      'major': 'Data Science', 'gpa': 3.236, 'expected_graduation': '2028', 'graduation_season': 'Spring 2028'},
        'work_authorization': True, 'requires_sponsorship': False,
        'screening_defaults': {'authorized_to_work_us': True, 'require_sponsorship': False,
                              'is_18_or_older': True, 'willing_to_relocate': True,
                              'outside_business_activities': False, 'how_did_you_hear': 'Social Media',
                              'social_media_source': 'Instagram', 'desired_salary': 'Open to discuss'},
        'gender': 'Male', 'race_ethnicity': 'Asian', 'veteran_status': 'No', 'disability': 'Decline to answer',
        'links': {'linkedin': 'https://example.test/profile'},
        'resume': {'primary': '/fixture/Resume.pdf'},
    }


@pytest.mark.parametrize(('field', 'expected'), [
    ('first_name', 'Fixture'), ('phone', '5550101234'), ('email', 'fixture@example.test'),
    ('school', 'University of California, San Diego'), ('degree', 'Bachelor of Science'),
    ('discipline', 'Data Science'), ('gpa', '3.236'), ('education_end_year', '2028'),
    ('work_authorization', 'Yes'), ('sponsorship_now', 'No'), ('sponsorship_future', 'No'),
    ('is_18_or_older', 'Yes'), ('willing_to_relocate', 'Yes'), ('outside_business_activities', 'No'),
    ('gender', 'Male'), ('race', 'Asian'), ('veteran', 'No'), ('disability', 'Decline to answer'),
    ('how_did_you_hear', 'Social Media'), ('social_media_source', 'Instagram'),
    ('desired_salary', 'Open to discuss'), ('city', 'Fairfax'), ('resume', '/fixture/Resume.pdf'),
])
def test_resolves_actual_profile_schema_without_agent_answer_input(field, expected):
    assert canonical().resolve_fact(profile(), field) == expected


@pytest.mark.parametrize(('field', 'value'), [
    ('gpa', '3.8'), ('degree', { 'exact_option': "Master's Degree"}),
    ('work_authorization', 'No'), ('sponsorship_now', True), ('education_end_year', '2027'),
    ('school', 'Other University'), ('security_clearance', 'Yes'),
])
def test_agent_supplied_conflicting_material_facts_are_rejected(field, value):
    module = canonical()
    assert hasattr(module, 'verify_profile_answers'), 'answer validator missing'
    with pytest.raises(module.CanonicalAnswerError, match='canonical profile'):
        module.verify_profile_answers(profile(), {field: value})


def test_matching_answers_accept_equivalent_typed_option_and_phone_values():
    module = canonical()
    assert hasattr(module, 'verify_profile_answers'), 'answer validator missing'
    module.verify_profile_answers(profile(), {'gpa': 3.236, 'work_authorization': True,
        'degree': {'exact_option': 'Bachelor of Science'}, 'phone': '(555) 010-1234'})


@pytest.mark.parametrize(('field', 'change'), [
    ('work_authorization', lambda p: p['screening_defaults'].update(authorized_to_work_us=False)),
    ('work_authorization', lambda p: p.update(work_authorization='false')),
    ('gpa', lambda p: p.update(application_facts={'gpa': '3.8'})),
    ('gpa', lambda p: p['education'].update(gpa=True)),
    ('gpa', lambda p: p['education'].update(gpa=float('nan'))),
    ('degree', lambda p: p['education'].update(degree='')),
    ('degree', lambda p: p['education'].update(degree=['Bachelor of Science'])),
    ('phone', lambda p: p['contact'].update(phone='***1234')),
])
def test_malformed_or_conflicting_canonical_sources_fail_closed(field, change):
    p = profile()
    change(p)
    with pytest.raises(canonical().CanonicalAnswerError, match='canonical profile'):
        canonical().resolve_fact(p, field)


def test_missing_material_facts_are_not_inferred_from_year_or_demographics():
    for field in ('education_start_month', 'education_end_month', 'hispanic_latino', 'security_clearance'):
        with pytest.raises(canonical().CanonicalAnswerError):
            canonical().resolve_fact(profile(), field)


def test_explicit_accepted_profile_extension_supplies_missing_dates_without_overriding_core():
    p = profile()
    p['application_facts'] = {'education_start_month': 'September', 'education_end_month': 'May'}
    assert canonical().resolve_fact(p, 'education_start_month') == 'September'
    assert canonical().resolve_fact(p, 'education_end_month') == 'May'


@pytest.mark.parametrize(('field', 'expected'), [('school', 'University of California - San Diego'),
    ('degree', "Bachelor's Degree"), ('current_degree', "Bachelor's"), ('discipline', 'Other')])
def test_schonfeld_aliases_are_explicit_and_tenant_scoped(field, expected):
    assert canonical().resolve_fact(profile(), field, tenant='schonfeld') == expected
    assert canonical().resolve_fact(profile(), field) != expected


def controls():
    return {'gpa': {'selector': '#gpa', 'operation': 'replace_text'},
            'work_authorization': {'selector': '#auth', 'operation': 'native_select'},
            'resume': {'selector': '#resume', 'operation': 'cdp_upload'}}


def test_review_resolves_all_controls_without_any_answer_actions():
    module = canonical()
    assert hasattr(module, 'canonical_review_fields'), 'independent Review grounding missing'
    assert module.canonical_review_fields(profile(), controls()) == {'#gpa': '3.236', '#auth': 'Yes'}
    assert module.canonical_review_fields(profile(), controls(), selectors=['#gpa']) == {'#gpa': '3.236'}


@pytest.mark.parametrize('change', [
    lambda c: c.update(clearance={'selector': '#clearance', 'operation': 'replace_text'}),
    lambda c: c['work_authorization'].update(selector='#gpa'),
])
def test_review_grounding_rejects_unknown_fact_or_ambiguous_control_map(change):
    module = canonical()
    assert hasattr(module, 'canonical_review_fields'), 'independent Review grounding missing'
    c = controls()
    change(c)
    with pytest.raises(module.CanonicalAnswerError):
        module.canonical_review_fields(profile(), c)


def test_review_grounding_rejects_unknown_observed_selector():
    module = canonical()
    assert hasattr(module, 'canonical_review_fields'), 'independent Review grounding missing'
    with pytest.raises(module.CanonicalAnswerError):
        module.canonical_review_fields(profile(), controls(), selectors=['#unmapped'])


@pytest.mark.parametrize(('field', 'expected'), [
    ('last_name', 'Person'), ('full_name', 'Fixture Person'), ('sponsorship', 'No'),
    ('requires_sponsorship', 'No'), ('authorized_to_work_us', 'Yes'),
    ('country', 'United States'), ('state', 'VA'), ('zip', '22032'),
    ('linkedin', 'https://example.test/profile'),
])
def test_resolves_common_learned_control_aliases(field, expected):
    assert canonical().resolve_fact(profile(), field) == expected


def test_conflicting_selected_option_cannot_hide_behind_correct_exact_option():
    with pytest.raises(canonical().CanonicalAnswerError):
        canonical().verify_profile_answers(profile(), {'degree': {'exact_option': 'Bachelor of Science',
                                                                'selected_option': 'Master of Science'}})


def test_actions_bind_semantic_fact_selector_operation_and_expected_value():
    module = canonical()
    assert hasattr(module, 'verify_actions'), 'canonical action validation missing'
    actions = [{'field': 'gpa', 'selector': '#gpa', 'operation': 'replace_text', 'value': '3.236'}]
    module.verify_actions(profile(), actions, controls())
    for change in ({'value': '3.8'}, {'expected_value': '3.8'}, {'selector': '#auth'}, {'operation': 'set_checked'}):
        with pytest.raises(module.CanonicalAnswerError):
            module.verify_actions(profile(), [{**actions[0], **change}], controls())
    with pytest.raises(module.CanonicalAnswerError):
        module.verify_actions(profile(), actions * 2, controls())
