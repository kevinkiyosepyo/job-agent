"""Synthetic facts for the exact combined sponsorship prompt in a public pilot."""
from answer_coverage import build_coverage_matrix
from question_engine import QuestionAnswerEngine

QUESTION = 'Will you now or will you in the future require employment visa sponsorship?'


def test_combined_sponsorship_uses_both_canonical_timeframes():
    profile = {'application_facts': {'sponsorship_now':'Yes', 'sponsorship_future':'No'}}
    answer = QuestionAnswerEngine(profile=profile).answer(QUESTION)
    assert answer.status == 'answered'
    assert answer.answer == 'Yes'
    assert answer.question_key == 'sponsorship_now_or_future'


def test_existing_combined_prompt_does_not_ignore_current_sponsorship():
    profile = {'application_facts': {'sponsorship_now':'Yes', 'sponsorship_future':'No'}}
    answer = QuestionAnswerEngine(profile=profile).answer('Will you now or in the future require sponsorship?')
    assert answer.answer == 'Yes'


def test_combined_answer_truth_table_and_global_fact():
    for now, future, expected in [('No','No','No'), ('Yes','No','Yes'), ('No','Yes','Yes'), ('Yes','Yes','Yes')]:
        profile = {'application_facts': {'sponsorship_now':now, 'sponsorship_future':future}}
        assert QuestionAnswerEngine(profile=profile).answer(QUESTION).answer == expected
    assert QuestionAnswerEngine(profile={'requires_sponsorship':False}).answer(QUESTION).answer == 'No'


def test_combined_answer_requires_both_facts_even_with_agent_proposed_answer():
    for facts in [{}, {'sponsorship_future':'No'}, {'sponsorship_now':'Yes'},
                  {'sponsorship_now_or_future':'No'}]:
        answer = QuestionAnswerEngine(profile={'application_facts':facts},
            google_doc_answers=[{'question_key':'sponsorship_now_or_future','answer':'No'}]).answer(QUESTION)
        assert answer.status == 'unknown'
        assert answer.reason == 'unknown_profile_fact'


def test_conflicting_or_malformed_timeframe_and_combined_fact_fail_closed():
    for profile in [
        {'requires_sponsorship':False, 'application_facts':{'sponsorship_now':'Yes'}},
        {'application_facts':{'sponsorship_now':'maybe','sponsorship_future':'No'}},
        {'application_facts':{'sponsorship_now':'No','sponsorship_future':'No','sponsorship_now_or_future':'Yes'}},
    ]:
        assert QuestionAnswerEngine(profile=profile).answer(QUESTION).status == 'conflict'


def test_combined_answer_is_independently_checked_for_review():
    import pytest
    from canonical_answers import CanonicalAnswerError, canonical_review_fields, verify_profile_answers
    profile = {'application_facts':{'sponsorship_now':'Yes','sponsorship_future':'No'}}
    controls = {'sponsorship_now_or_future':{'selector':'#synthetic-sponsor','operation':'native_select'}}
    assert canonical_review_fields(profile, controls) == {'#synthetic-sponsor':'Yes'}
    with pytest.raises(CanonicalAnswerError, match='conflicting'):
        verify_profile_answers(profile, {'sponsorship_now_or_future':'No'})


def test_combined_question_does_not_match_negation_or_compound_legal_claims():
    engine = QuestionAnswerEngine(profile={'requires_sponsorship':False})
    for question in [QUESTION + ' Explain why.',
                     'Will you now or will you in the future NOT require employment visa sponsorship?',
                     'Will you now or will you in the future require employment visa sponsorship or relocation assistance?']:
        assert engine.answer(question).reason == 'unknown_question'


def test_combined_fact_still_requires_exact_radio_option():
    from prepare_job import prepare_saved_html
    from prepare_live_job import _questions_from_fields
    html = '<li class="application-question"><div class="application-label">' + QUESTION + '</div><label><input type="radio" name="sponsor" value="no" required>No</label></li>'
    payload = prepare_saved_html(html_text=html, page_url='https://jobs.lever.co/example/1/apply')
    matrix = build_coverage_matrix(profile={'requires_sponsorship':True}, questions=_questions_from_fields(payload))
    assert matrix['known'] == []
    assert matrix['human_required'][0]['reason'] == 'answer_not_in_native_options'
