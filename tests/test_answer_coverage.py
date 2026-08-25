from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from answer_coverage import build_coverage_matrix


def test_coverage_matrix_reports_profile_answer_as_known():
    matrix = build_coverage_matrix(
        profile={"education": {"graduation_season": "Spring 2028"}},
        questions=[{"label": "What is your expected graduation date?", "required": True}],
    )

    assert matrix == {
        "known": [
            {
                "question": "What is your expected graduation date?",
                "question_key": "graduation_season",
                "source": "profile",
            }
        ],
        "company_specific": [],
        "optional_skip": [],
        "human_required": [],
    }


def test_coverage_matrix_separates_company_specific_doc_answer():
    matrix = build_coverage_matrix(
        profile={},
        company="BNY",
        google_doc_answers=[
            {
                "company": "BNY",
                "question_key": "how_did_you_hear",
                "answer": "Instagram",
            }
        ],
        questions=[{"label": "How did you hear about BNY?", "required": True}],
    )

    assert matrix["company_specific"] == [
        {
            "question": "How did you hear about BNY?",
            "question_key": "how_did_you_hear",
            "source": "google_doc:company",
        }
    ]


def test_coverage_matrix_skips_optional_questions_and_escalates_unknown_required_ones():
    matrix = build_coverage_matrix(
        profile={},
        questions=[
            {"label": "Optional portfolio URL", "required": False},
            {"label": "What is your security clearance?", "required": True},
        ],
    )

    assert matrix["optional_skip"] == [
        {"question": "Optional portfolio URL", "question_key": "unknown"}
    ]
    assert matrix["human_required"] == [
        {
            "question": "What is your security clearance?",
            "question_key": "unknown",
            "reason": "unknown_question",
        }
    ]
