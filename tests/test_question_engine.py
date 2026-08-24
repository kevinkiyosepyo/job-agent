from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from question_engine import QuestionAnswerEngine


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
        profile=make_profile(),
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
        profile=make_profile(),
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
