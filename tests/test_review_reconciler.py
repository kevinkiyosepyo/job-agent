from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


PAGE_URL = "https://sanitized.example.test/apply/REQ-123"
EXPECTED_TARGET = {
    "target_id": "page-42",
    "page_url": PAGE_URL,
    "company": "Sanitized Example",
    "role": "Software Engineer Intern",
    "requisition": "REQ-123",
}


def prepared_review() -> dict:
    return {
        "target_id": "page-42",
        "page_url": PAGE_URL,
        "identity": {
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
        },
        "submission_enabled": False,
        "review_ready": True,
        "answer_coverage": {"human_required": []},
        "applied_answers": {
            "verified": True,
            "field_evidence": [
                {"selector": "#first-name", "verified": True},
                {"selector": "#school", "verified": True},
            ],
        },
        "evidence": {
            "sanitized": True,
            "target_bound": True,
            "answer_values_persisted": False,
        },
    }


def server_review() -> dict:
    return {
        "source": "server_saved_review",
        "server_saved": True,
        "target_id": "page-42",
        "page_url": PAGE_URL,
        "identity": {
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
        },
        "fields": {
            "#first-name": "Fixture Person",
            "#school": "Fixture University",
            "work_authorization": "Yes",
        },
        "resume": {"basename": "Resume.pdf", "sha256": "a" * 64},
        "parser_repairs": [{"field": "#school", "verified": True}],
        "questions": [
            {
                "id": "work_authorization",
                "required": True,
                "answered": True,
                "verified": True,
            }
        ],
    }


def test_reconciler_makes_exact_server_review_authoritative_without_persisting_values():
    import review_reconciler

    result = review_reconciler.reconcile_review(
        preparation_evidence=prepared_review(),
        server_review=server_review(),
        expected_target=EXPECTED_TARGET,
        profile_fields={
            "#first-name": "Fixture Person",
            "#school": "Fixture University",
            "work_authorization": "Yes",
        },
        resume_preflight={
            "basename": "Resume.pdf",
            "content_type": "application/pdf",
            "sha256": "a" * 64,
            "verified": True,
        },
        required_parser_repairs=["#school"],
        required_question_ids=["work_authorization"],
    )

    assert result["review_authoritative"] is True
    assert result["submission_authorized"] is False
    assert result["binding"] == {**EXPECTED_TARGET, "verified": True}
    assert result["fields"] == [
        {"field": "#first-name", "verified": True},
        {"field": "#school", "verified": True},
        {"field": "work_authorization", "verified": True},
    ]
    assert result["resume"] == {"basename": "Resume.pdf", "verified": True}
    assert result["parser_repairs"] == [{"field": "#school", "verified": True}]
    assert result["required_questions"] == [
        {"question_id": "work_authorization", "verified": True}
    ]
    assert result["human_required"] == []
    assert len(result["review_evidence_sha256"]) == 64
    serialized = json.dumps(result)
    assert "Fixture Person" not in serialized
    assert "Fixture University" not in serialized
    assert "a" * 64 not in serialized


def test_reconciler_accepts_exact_profile_selected_resume_basename():
    import review_reconciler

    rendered = server_review()
    rendered["resume"]["basename"] = "Resume 2027 SWE.pdf"
    result = review_reconciler.reconcile_review(
        preparation_evidence=prepared_review(),
        server_review=rendered,
        expected_target=EXPECTED_TARGET,
        profile_fields={
            "#first-name": "Fixture Person",
            "#school": "Fixture University",
            "work_authorization": "Yes",
        },
        resume_preflight={
            "basename": "Resume 2027 SWE.pdf",
            "content_type": "application/pdf",
            "sha256": "a" * 64,
            "verified": True,
        },
        required_parser_repairs=["#school"],
        required_question_ids=["work_authorization"],
    )

    assert result["review_authoritative"] is True
    assert result["resume"] == {
        "basename": "Resume 2027 SWE.pdf",
        "verified": True,
    }


def test_reconciler_rejects_filename_only_resume_even_when_marked_verified():
    import review_reconciler

    rendered = server_review()
    rendered["resume"] = {
        "basename": "Resume 2027 SWE.pdf",
        "sha256": "",
        "verified": True,
    }
    result = review_reconciler.reconcile_review(
        preparation_evidence=prepared_review(),
        server_review=rendered,
        expected_target=EXPECTED_TARGET,
        profile_fields={
            "#first-name": "Fixture Person",
            "#school": "Fixture University",
            "work_authorization": "Yes",
        },
        resume_preflight={
            "basename": "Resume 2027 SWE.pdf",
            "content_type": "application/pdf",
            "sha256": "a" * 64,
            "verified": True,
        },
        required_parser_repairs=["#school"],
        required_question_ids=["work_authorization"],
    )

    assert result["review_authoritative"] is False
    assert result["resume"] == {
        "basename": "Resume 2027 SWE.pdf",
        "verified": False,
    }


def test_reconciler_keeps_every_unresolved_review_difference_human_required():
    import review_reconciler

    rendered = server_review()
    rendered["page_url"] = "https://sanitized.example.test/apply/OTHER"
    rendered["fields"]["#first-name"] = "Wrong fixture value"
    rendered["resume"] = {"basename": "Other.pdf", "sha256": "wrong-sha256"}
    rendered["parser_repairs"] = [{"field": "#school", "verified": False}]
    rendered["questions"][0]["answered"] = False

    result = review_reconciler.reconcile_review(
        preparation_evidence=prepared_review(),
        server_review=rendered,
        expected_target=EXPECTED_TARGET,
        profile_fields={
            "#first-name": "Fixture Person",
            "#school": "Fixture University",
            "work_authorization": "Yes",
        },
        resume_preflight={
            "basename": "Resume.pdf",
            "content_type": "application/pdf",
            "sha256": "a" * 64,
            "verified": True,
        },
        required_parser_repairs=["#school"],
        required_question_ids=["work_authorization"],
    )

    assert result["review_authoritative"] is False
    assert result["submission_authorized"] is False
    assert {item["type"] for item in result["human_required"]} == {
        "target_identity_mismatch",
        "profile_field_mismatch",
        "resume_not_exact",
        "parser_repair_unverified",
        "required_question_unanswered",
    }
    assert all("expected" not in item and "actual" not in item for item in result["human_required"])
