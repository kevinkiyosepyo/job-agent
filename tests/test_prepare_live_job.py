from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeLivePage:
    target_id = "page-42"

    def read_only_snapshot(self) -> dict[str, object]:
        return {
            "target_id": "page-42",
            "url": "https://job-boards.greenhouse.io/example/jobs/123",
            "html": "<html>fixture</html>",
            "read_only": True,
        }


def test_prepare_live_job_binds_exact_target_verifies_identity_and_stays_non_submitting():
    import prepare_live_job

    result = prepare_live_job.prepare_live_job(
        page=FakeLivePage(),
        target_id="page-42",
        expected_url="https://job-boards.greenhouse.io/example/jobs/123",
        expected_identity={
            "company": "Example Inc",
            "role": "Software Engineer Intern",
            "requisition": "123",
        },
        profile={"name": "Kevin"},
        prepare=lambda **kwargs: {
            "platform": "greenhouse",
            "company": "Example Inc",
            "role": "Software Engineer Intern",
            "requisition": "123",
            "questions": [],
            "submission_enabled": False,
        },
        coverage=lambda **kwargs: {"known": [], "company_specific": [], "optional_skip": [], "human_required": []},
        approved_answers={"#first-name": "Kevin"},
        apply_known=lambda answers: {
            "action": "fill_known_page",
            "field_evidence": [{"selector": "#first-name", "expected": answers["#first-name"], "actual": "Kevin", "verified": True}],
            "verified": True,
        },
    )

    assert result == {
        "target_id": "page-42",
        "page_url": "https://job-boards.greenhouse.io/example/jobs/123",
        "identity": {"company": "Example Inc", "role": "Software Engineer Intern", "requisition": "123"},
        "platform": "greenhouse",
        "submission_enabled": False,
        "review_ready": True,
        "answer_coverage": {"known": [], "company_specific": [], "optional_skip": [], "human_required": []},
        "applied_answers": {
            "action": "fill_known_page",
            "field_evidence": [{"selector": "#first-name", "expected": "Kevin", "actual": "Kevin", "verified": True}],
            "verified": True,
        },
        "evidence": {"sanitized": True, "target_bound": True},
    }


def test_prepare_live_job_rejects_target_or_identity_drift_before_handler_dispatch():
    import prepare_live_job

    with pytest.raises(prepare_live_job.LivePreparationError, match="target URL changed"):
        prepare_live_job.prepare_live_job(
            page=FakeLivePage(),
            target_id="page-42",
            expected_url="https://job-boards.greenhouse.io/example/jobs/other",
            expected_identity={"company": "Example Inc", "role": "Software Engineer Intern", "requisition": "123"},
            profile={},
            prepare=lambda **kwargs: pytest.fail("handler must not run"),
            coverage=lambda **kwargs: pytest.fail("coverage must not run"),
        )
