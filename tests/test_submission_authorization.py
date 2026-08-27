from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def authoritative_review() -> dict:
    artifact = {
        "review_authoritative": True,
        "submission_authorized": False,
        "binding": {
            "target_id": "page-42",
            "page_url": "https://sanitized.example.test/apply/REQ-123",
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
            "verified": True,
        },
        "fields": [{"field": "#first-name", "verified": True}],
        "resume": {"basename": "Resume.pdf", "verified": True},
        "parser_repairs": [],
        "required_questions": [
            {"question_id": "work_authorization", "verified": True}
        ],
        "human_required": [],
        "evidence": {"sanitized": True, "review_authority_only": True},
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["review_evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return artifact


def current_binding(review: dict) -> dict:
    return {
        "job_id": 17,
        "target_id": review["binding"]["target_id"],
        "page_url": review["binding"]["page_url"],
        "requisition": review["binding"]["requisition"],
        "review_evidence_sha256": review["review_evidence_sha256"],
    }


def test_authorization_is_exact_bound_stored_as_digest_consumed_once_and_rejects_replay(tmp_path):
    import submission_authorization

    database = tmp_path / "authorization.db"
    review = authoritative_review()
    store = submission_authorization.SubmissionAuthorizationStore(database)

    issued = store.issue(
        job_id=17,
        review_evidence=review,
        actor="fixture-operator",
        issued_at="2026-08-27T08:00:00+00:00",
        expires_at="2026-08-27T08:05:00+00:00",
    )

    assert issued["binding"] == {
        **current_binding(review),
        "actor": "fixture-operator",
    }
    assert issued["single_use"] is True
    assert issued["expires_at"] == "2026-08-27T08:05:00+00:00"
    token = issued["token"]
    assert token.encode() not in database.read_bytes()

    consumed = store.consume(
        token=token,
        current_binding=current_binding(review),
        actor="fixture-operator",
        now="2026-08-27T08:01:00+00:00",
    )

    assert consumed == {
        "authorization_consumed": True,
        "single_use": True,
        "binding": {**current_binding(review), "actor": "fixture-operator"},
        "expires_at": "2026-08-27T08:05:00+00:00",
        "consumed_at": "2026-08-27T08:01:00+00:00",
    }
    with pytest.raises(PermissionError, match="replayed"):
        store.consume(
            token=token,
            current_binding=current_binding(review),
            actor="fixture-operator",
            now="2026-08-27T08:02:00+00:00",
        )


def test_target_or_review_drift_permanently_invalidates_authorization(tmp_path):
    import submission_authorization

    review = authoritative_review()
    store = submission_authorization.SubmissionAuthorizationStore(tmp_path / "authorization.db")
    issued = store.issue(
        job_id=17,
        review_evidence=review,
        actor="fixture-operator",
        issued_at="2026-08-27T08:00:00+00:00",
        expires_at="2026-08-27T08:05:00+00:00",
    )
    drifted = current_binding(review)
    drifted["page_url"] = "https://sanitized.example.test/apply/OTHER"

    with pytest.raises(PermissionError, match="binding drift"):
        store.consume(
            token=issued["token"],
            current_binding=drifted,
            actor="fixture-operator",
            now="2026-08-27T08:01:00+00:00",
        )
    with pytest.raises(PermissionError, match="invalidated"):
        store.consume(
            token=issued["token"],
            current_binding=current_binding(review),
            actor="fixture-operator",
            now="2026-08-27T08:02:00+00:00",
        )


def test_authorization_rejects_expiry_or_non_authoritative_review(tmp_path):
    import submission_authorization

    review = authoritative_review()
    store = submission_authorization.SubmissionAuthorizationStore(tmp_path / "authorization.db")
    issued = store.issue(
        job_id=17,
        review_evidence=review,
        actor="fixture-operator",
        issued_at="2026-08-27T08:00:00+00:00",
        expires_at="2026-08-27T08:05:00+00:00",
    )

    with pytest.raises(PermissionError, match="expired"):
        store.consume(
            token=issued["token"],
            current_binding=current_binding(review),
            actor="fixture-operator",
            now="2026-08-27T08:05:00+00:00",
        )

    blocked = authoritative_review()
    blocked["review_authoritative"] = False
    with pytest.raises(ValueError, match="authoritative Review"):
        store.issue(
            job_id=17,
            review_evidence=blocked,
            actor="fixture-operator",
            issued_at="2026-08-27T08:00:00+00:00",
            expires_at="2026-08-27T08:05:00+00:00",
        )
