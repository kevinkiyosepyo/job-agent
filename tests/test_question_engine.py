from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from question_engine import QuestionAnswerEngine
import pytest


@pytest.mark.parametrize('question', ['Do you hold a security clearance?', 'Have you been debarred from government contracts?'])
def test_unknown_question_never_looks_up_universal_unknown_doc_key(question):
    engine = QuestionAnswerEngine(profile={}, google_doc_answers=[{'question_key': 'unknown', 'answer': 'Yes'}])
    result = engine.answer(question)
    assert result.status == 'unknown'
    assert result.answer is None


def make_profile() -> dict:
    return {
        "contact": {"email": "kevinkpyo@gmail.com"},
        "education": {"graduation_season": "Spring 2028"},
        "screening_defaults": {
            "authorized_to_work_us": True,
            "require_sponsorship": False,
            "how_did_you_hear": "Social Media",
            "social_media_source": "Instagram",
        },
        "experience": [
            {
                "company": "HIV Neurobehavioral Research Center",
                "title": "IT Student Assistant IV Support",
                "start": "2026",
            }
        ],
    }


def test_answer_uses_profile_fact_before_conflicting_google_doc_value():
    engine = QuestionAnswerEngine(
        profile=make_profile(),
        google_doc_answers=[
            {
                "question_key": "graduation_season",
                "answer": "Winter 2027",
            }
        ],
    )

    result = engine.answer("What is your expected graduation date?")

    assert result.status == "answered"
    assert result.answer == "Spring 2028"
    assert result.source == "profile"



def test_answer_prefers_company_specific_google_doc_entry_over_generic_one():
    engine = QuestionAnswerEngine(
        profile={},
        google_doc_answers=[
            {
                "question_key": "how_did_you_hear",
                "answer": "Social Media",
            },
            {
                "company": "BNY",
                "question_key": "how_did_you_hear",
                "answer": "Instagram",
            },
        ],
    )

    result = engine.answer("How did you hear about BNY?", company="BNY")

    assert result.status == "answered"
    assert result.answer == "Instagram"
    assert result.source == "google_doc:company"



def test_answer_fails_closed_when_exact_start_month_is_unknown():
    engine = QuestionAnswerEngine(profile=make_profile(), google_doc_answers=[])

    result = engine.answer("What month did you start at HNRC?")

    assert result.status == "unknown"
    assert result.reason == "unknown_profile_fact"
    assert result.question_key == "experience_start_month"



def test_answer_fails_closed_when_company_specific_google_doc_answers_conflict():
    engine = QuestionAnswerEngine(
        profile={},
        google_doc_answers=[
            {
                "company": "BNY",
                "question_key": "how_did_you_hear",
                "answer": "Instagram",
            },
            {
                "company": "BNY",
                "question_key": "how_did_you_hear",
                "answer": "Facebook",
            },
        ],
    )

    result = engine.answer("How did you hear about BNY?", company="BNY")

    assert result.status == "conflict"
    assert result.reason == "conflicting_google_doc_answers"
    assert result.question_key == "how_did_you_hear"


@pytest.mark.parametrize(('question', 'answer'), [
    ('What is your GPA?', '3.236'), ('What degree are you pursuing?', 'Bachelor of Science'),
    ('What is your major?', 'Data Science'), ('What university do you attend?', 'University of California, San Diego'),
    ('Are you legally authorized to work in the United States?', 'Yes'),
    ('Will you now or in the future require sponsorship?', 'No'),
    ('Are you 18 years of age or older?', 'Yes'), ('Are you willing to relocate?', 'Yes'),
    ('Do you have outside business activities?', 'No'), ('What is your gender?', 'Male'),
    ('What is your race/ethnicity?', 'Asian'), ('What is your veteran status?', 'No'),
    ('What is your disability status?', 'Decline to answer'),
    ('How did you hear about this role?', 'Social Media'), ('Which social media source?', 'Instagram'),
    ('What is your desired salary?', 'Open to discuss'),
])
def test_ordinary_known_questions_are_sourced_canonically(question, answer):
    from test_canonical_answers import profile
    result = QuestionAnswerEngine(profile=profile(), google_doc_answers=[{'question_key':'unknown','answer':'Wrong'}]).answer(question)
    assert result.status == 'answered'
    assert result.answer == answer
    assert result.source == 'profile'


def test_profile_referral_policy_beats_historical_company_doc_entry():
    result = QuestionAnswerEngine(profile=make_profile(), google_doc_answers=[
        {'question_key':'how_did_you_hear','company':'BNY','answer':'Instagram'}]).answer('How did you hear about BNY?',company='BNY')
    assert result.answer == 'Social Media'
    assert result.source == 'profile'


@pytest.mark.parametrize(('question', 'key'), [
    ('What is your GPA?', 'gpa'), ('What degree are you pursuing?', 'degree'),
    ('What is your expected graduation date?', 'graduation_season'),
    ('What month did you start at HNRC?', 'experience_start_month'),
])
def test_unknown_material_fact_cannot_be_filled_by_historical_doc(question, key):
    result = QuestionAnswerEngine(profile={}, google_doc_answers=[{'question_key':key,'answer':'Unconfirmed'}]).answer(question)
    assert result.status == 'unknown'
    assert result.answer is None


def test_conflicting_profile_authorization_fails_closed_without_doc_fallback():
    p = make_profile()
    p['work_authorization'] = False
    result = QuestionAnswerEngine(profile=p).answer('Are you legally authorized to work in the United States?')
    assert result.status == 'conflict'
    assert result.answer is None


@pytest.mark.parametrize('question', [
    'Is your graduation between January and May 2027?',
    'Do you meet the graduation requirement?', 'Do you meet the minimum GPA of 3.5?',
    'Are you legally authorized to work in Canada?',
    'What month can you start after graduation?',
])
def test_related_but_materially_different_questions_are_not_reclassified(question):
    from test_canonical_answers import profile
    result = QuestionAnswerEngine(profile=profile()).answer(question)
    assert result.status == 'unknown'
    assert result.answer is None


@pytest.mark.parametrize(('question', 'expected'), [
    ('Are you authorized to work in the US?', 'Yes'),
    ('Are you legally authorized to work in the U.S.?', 'Yes'),
    ('Will you require sponsorship?', 'No'), ('Do you require visa sponsorship?', 'No'),
    ('Are you at least 18 years old?', 'Yes'), ('Are you willing to relocate for this role?', 'Yes'),
    ('Cumulative GPA', '3.236'), ('Current degree', 'Bachelor of Science'),
    ('Gender', 'Male'), ('Disability status', 'Decline to answer'),
])
def test_common_equivalent_default_question_wordings(question, expected):
    from test_canonical_answers import profile
    result = QuestionAnswerEngine(profile=profile()).answer(question)
    assert result.status == 'answered'
    assert result.answer == expected
    assert result.source == 'profile'
