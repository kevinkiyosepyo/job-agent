"""Synthetic school prompt from a saved SWE pilot; no employer/applicant data."""
from answer_coverage import build_coverage_matrix
from lever_handler import inspect_html
from prepare_live_job import _questions_from_fields


def test_name_of_school_question_reaches_canonical_fact_and_native_option_check():
    html = '<label for="school">Name of School</label><select id="school" required><option value="">Other</option><option value="example">Example University</option></select>'
    fields = _questions_from_fields(inspect_html(html, page_url='https://jobs.lever.co/example/1/apply'))
    matrix = build_coverage_matrix(profile={'education':{'university':'Example University'}}, questions=fields)
    assert matrix['human_required'] == []
    assert matrix['known'] == [{'question':'Name of School','question_key':'school','source':'profile'}]


def test_school_prompt_does_not_guess_prior_or_conditional_institutions():
    from question_engine import QuestionAnswerEngine
    engine = QuestionAnswerEngine(profile={'education':{'university':'Example University'}})
    for question in ['Name of High School', 'Name of School you previously attended',
                     'Name of School if different from current school', 'Name of School and graduation year']:
        assert engine.answer(question).status == 'unknown'


def test_school_alias_preserves_missing_and_conflicting_profile_failure():
    from question_engine import QuestionAnswerEngine
    assert QuestionAnswerEngine(profile={}).answer('Name of School').reason == 'unknown_profile_fact'
    profile = {'education':{'university':'Example University'},'application_facts':{'school':'Conflicting University'}}
    assert QuestionAnswerEngine(profile=profile).answer('Name of School').status == 'conflict'


def test_school_alias_does_not_guess_a_similar_directory_label():
    html = '<label for="school">Name of School</label><select id="school" required><option value="other">Example State University</option></select>'
    questions = _questions_from_fields(inspect_html(html, page_url='https://jobs.lever.co/example/1/apply'))
    matrix = build_coverage_matrix(profile={'education':{'university':'Example University'}}, questions=questions)
    assert matrix['known'] == []
    assert matrix['human_required'][0]['reason'] == 'answer_not_in_native_options'
