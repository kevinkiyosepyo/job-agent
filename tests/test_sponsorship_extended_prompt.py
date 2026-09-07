"""Synthetic profiles exercising one whole sponsorship wording observed on a public pilot."""
from question_engine import QuestionAnswerEngine

QUESTION = ('Do you now, or will you in the future, need sponsorship from an employer '
            'in order to obtain, extend or renew your authorization to work in the United States?')


def test_extended_sponsorship_prompt_resolves_both_timeframes():
    engine = QuestionAnswerEngine(profile={'application_facts': {
        'sponsorship_now': 'Yes', 'sponsorship_future': 'No'}})
    result = engine.answer(QUESTION)
    assert result.status == 'answered'
    assert result.question_key == 'sponsorship_now_or_future'
    assert result.answer == 'Yes'


def test_extended_prompt_preserves_truth_table_and_global_fact():
    for now, future, expected in [('No','No','No'), ('Yes','No','Yes'), ('No','Yes','Yes'), ('Yes','Yes','Yes')]:
        engine = QuestionAnswerEngine(profile={'application_facts': {
            'sponsorship_now': now, 'sponsorship_future': future}})
        assert engine.answer(QUESTION).answer == expected
    assert QuestionAnswerEngine(profile={'requires_sponsorship':False}).answer(QUESTION).answer == 'No'


def test_extended_prompt_does_not_borrow_missing_timeframes_from_proposed_answers():
    for facts in ({}, {'sponsorship_now':'No'}, {'sponsorship_future':'No'}, {'sponsorship_now_or_future':'No'}):
        engine = QuestionAnswerEngine(profile={'application_facts': facts}, google_doc_answers=[{
            'question_key':'sponsorship_now_or_future', 'answer':'No'}])
        result = engine.answer(QUESTION)
        assert result.status == 'unknown'
        assert result.reason == 'unknown_profile_fact'


def test_extended_prompt_preserves_conflicting_and_malformed_fact_rejection():
    for profile in (
        {'requires_sponsorship':False, 'application_facts': {'sponsorship_now':'Yes'}},
        {'application_facts': {'sponsorship_now':'maybe','sponsorship_future':'No'}},
        {'application_facts': {'sponsorship_now':'No','sponsorship_future':'No','sponsorship_now_or_future':'Yes'}},
    ):
        assert QuestionAnswerEngine(profile=profile).answer(QUESTION).status == 'conflict'


def test_extended_prompt_does_not_match_other_jurisdictions_negations_or_extra_claims():
    engine = QuestionAnswerEngine(profile={'requires_sponsorship':False})
    for question in (QUESTION.replace('United States','Canada'), QUESTION.replace('need sponsorship','not need sponsorship'),
                     QUESTION+' Explain why.', QUESTION.replace('sponsorship from','sponsorship or relocation assistance from'),
                     QUESTION.replace('Do you now, or will you in the future,','Will you in the future')):
        assert engine.answer(question).reason == 'unknown_question'


def test_extended_prompt_still_requires_offered_native_option():
    from answer_coverage import build_coverage_matrix
    question = {'label':QUESTION, 'required':True, 'native_radio': {
        'source':'static_html','type':'radio','options':[{'label':'No','value':'no','disabled':False}]}}
    coverage = build_coverage_matrix(profile={'requires_sponsorship':True}, questions=[question])
    assert coverage['known'] == []
    assert coverage['human_required'][0]['reason'] == 'answer_not_in_native_options'


def test_extended_prompt_maps_to_independently_checked_review_fact():
    import pytest
    from canonical_answers import CanonicalAnswerError, verify_profile_answers
    profile = {'application_facts': {'sponsorship_now':'Yes','sponsorship_future':'No'}}
    result = QuestionAnswerEngine(profile=profile).answer(QUESTION)
    with pytest.raises(CanonicalAnswerError, match='conflicting'):
        verify_profile_answers(profile, {result.question_key:'No'})
