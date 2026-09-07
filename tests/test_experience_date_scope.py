"""Synthetic reduced dates/employers from an observed generic education-label collision."""
from question_engine import QuestionAnswerEngine
from answer_coverage import build_coverage_matrix
import pytest


@pytest.mark.parametrize('question', [
    'Start month', 'Start date month', 'Education start date month',
    'Please select the month you will be able to start your internship.',
    'What month can you start after graduation?', 'What month did you start at school?',
    'What month did you start at Other Labs and why?',
    'What month did you start at Other Labs after graduation?',
    'What month did you start at Another Other Labs?',
    'What month did you start at Other Labs or Sample?',
])
def test_generic_conditional_compound_or_approximate_date_prompts_stay_unknown(question):
    result=QuestionAnswerEngine(profile={'experience':[{'company':'Other Labs','start':'2024-09'},
        {'company':'Sample','start':'2025-02'}]},google_doc_answers=[
        {'question_key':'experience_start_month','answer':'Unconfirmed'}]).answer(question)
    assert result.status=='unknown'
    assert result.answer is None


@pytest.mark.parametrize('employer', ['Other Labs','OL','other labs','  Other   Labs  '])
def test_unique_exact_employer_or_acronym_preserves_supported_month(employer):
    result=QuestionAnswerEngine(profile={'experience':[{'company':'Other Labs','start':'2024-09'}]}).answer(f'What month did you start at {employer}?')
    assert result.status=='answered'
    assert result.answer=='September'
    assert result.source=='profile'


@pytest.mark.parametrize('records', [
    [{'company':'Other Labs','start':'2024-09'},{'company':'Open Library','start':'2025-02'}],
    [{'company':'Other Labs','start':'2024-09'},{'company':'Other Labs'}],
    [{'company':'Other Labs','start':'2024-09'},{'company':'Other Labs','start':'2024-09'}],
])
def test_ambiguous_record_or_acronym_does_not_choose_even_with_equal_months(records):
    result=QuestionAnswerEngine(profile={'experience':records}).answer('What month did you start at OL?')
    assert result.status=='unknown'
    assert result.answer is None


@pytest.mark.parametrize('start', [None,'','2024','2024-00','2024-13','unknown'])
def test_exact_employer_without_supported_month_remains_unknown(start):
    result=QuestionAnswerEngine(profile={'experience':[{'company':'Other Labs','start':start}]}).answer('What month did you start at Other Labs?')
    assert result.status=='unknown'
    assert result.answer is None


def test_generic_education_month_does_not_match_an_employer_acronym_substring():
    profile={'experience':[{'company':'Sample','start':'2025-02'}]}
    result=QuestionAnswerEngine(profile=profile).answer('Start date month')
    assert result.status=='unknown'
    assert result.answer is None
    coverage=build_coverage_matrix(profile=profile,questions=[{'label':'Start date month','required':True}])
    assert coverage['known']==[]
    assert len(coverage['human_required'])==1


def test_employer_target_is_exact_not_an_alias_substring_in_the_question():
    profile={'experience':[{'company':'Sample','start':'2025-02'}, {'company':'Other Labs','start':'2024-09'}]}
    result=QuestionAnswerEngine(profile=profile).answer('What month did you start at Other Labs?')
    assert result.status=='answered'
    assert result.answer=='September'


def test_multiple_matching_experience_records_do_not_choose_the_first_date():
    profile={'experience':[{'company':'Other Labs','start':'2025-02'}, {'company':'Other Labs','start':'2024-09'}]}
    result=QuestionAnswerEngine(profile=profile).answer('What month did you start at Other Labs?')
    assert result.status=='unknown'
    assert result.answer is None
