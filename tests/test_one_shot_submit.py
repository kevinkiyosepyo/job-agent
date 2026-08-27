from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


PAGE_URL = "https://sanitized.example.test/apply/REQ-123"


def review_artifact() -> dict:
    artifact = {
        "review_authoritative": True,
        "submission_authorized": False,
        "binding": {
            "target_id": "page-42",
            "page_url": PAGE_URL,
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
            "verified": True,
        },
        "human_required": [],
        "evidence": {"sanitized": True, "review_authority_only": True},
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["review_evidence_sha256"] = hashlib.sha256(canonical).hexdigest()
    return artifact


def issue_authorization(tmp_path):
    import submission_authorization

    review = review_artifact()
    store = submission_authorization.SubmissionAuthorizationStore(tmp_path / "authorization.db")
    issued = store.issue(
        job_id=17,
        review_evidence=review,
        actor="fixture-operator",
        issued_at="2026-08-27T08:00:00+00:00",
        expires_at="2026-08-27T08:05:00+00:00",
    )
    return store, issued["token"], review["review_evidence_sha256"]


class ExactSubmitPage:
    def __init__(self, journal_path: Path, *, gates=None, maango=False, interruption=False):
        self.journal_path = journal_path
        self.gates = list(gates or [])
        self.maango = maango
        self.interruption = interruption
        self.click_count = 0
        self.confirmed = not interruption

    def read_only_snapshot(self) -> dict:
        return {
            "read_only": True,
            "target_id": "page-42",
            "url": PAGE_URL,
            "identity": {"requisition": "REQ-123"},
            "gates": self.gates,
            "maango": self.maango,
        }

    def inspect_submit_control(self, selector: str) -> dict:
        return {
            "selector": selector,
            "target_id": "page-42",
            "url": PAGE_URL,
            "visible": True,
            "enabled": True,
            "unique": True,
            "role": "button",
        }

    def click_submit_once(self, selector: str) -> None:
        intent = json.loads(self.journal_path.read_text().splitlines()[-1])
        assert intent["action"] == "submit"
        assert intent["evidence"]["status"] == "intent_recorded"
        assert intent["evidence"]["verified"] is False
        self.click_count += 1
        if self.interruption:
            import one_shot_submit

            raise one_shot_submit.SubmitInterrupted("fixture connection interrupted")

    def inspect_confirmation(self) -> dict:
        return {"confirmed": self.confirmed, "state": "submitted" if self.confirmed else "unknown"}


def execute(operator_module, *, store, token, page, journal_path, review_hash, maango_approved=False):
    return operator_module.execute_one_shot_submit(
        authorization_store=store,
        token=token,
        page=page,
        journal_path=journal_path,
        job_id=17,
        target_id="page-42",
        expected_url=PAGE_URL,
        requisition="REQ-123",
        review_evidence_sha256=review_hash,
        actor="fixture-operator",
        now="2026-08-27T08:01:00+00:00",
        submit_selector="#submit-application",
        maango_approved=maango_approved,
    )


def test_one_shot_submit_consumes_authorization_journals_intent_then_clicks_once(tmp_path):
    import one_shot_submit

    journal_path = tmp_path / "page-actions.jsonl"
    store, token, review_hash = issue_authorization(tmp_path)
    page = ExactSubmitPage(journal_path)

    result = execute(
        one_shot_submit,
        store=store,
        token=token,
        page=page,
        journal_path=journal_path,
        review_hash=review_hash,
    )

    assert result["status"] == "confirmation_observed"
    assert result["authorization_consumed"] is True
    assert result["one_shot"] is True
    assert result["replay_allowed"] is False
    assert page.click_count == 1
    entries = [json.loads(line) for line in journal_path.read_text().splitlines()]
    assert [entry["evidence"]["verified"] for entry in entries] == [False, True]
    with pytest.raises(PermissionError, match="replayed"):
        execute(
            one_shot_submit,
            store=store,
            token=token,
            page=page,
            journal_path=journal_path,
            review_hash=review_hash,
        )
    assert page.click_count == 1


def test_submit_interruption_inspects_confirmation_and_never_replays(tmp_path):
    import one_shot_submit

    journal_path = tmp_path / "page-actions.jsonl"
    store, token, review_hash = issue_authorization(tmp_path)
    page = ExactSubmitPage(journal_path, interruption=True)

    result = execute(
        one_shot_submit,
        store=store,
        token=token,
        page=page,
        journal_path=journal_path,
        review_hash=review_hash,
    )

    assert result == {
        "status": "blocked",
        "blocker": "submit interrupted without confirmation",
        "next_action": "inspect_confirmation_without_replay",
        "authorization_consumed": True,
        "one_shot": True,
        "replay_allowed": False,
    }
    assert page.click_count == 1
    with pytest.raises(PermissionError, match="replayed"):
        execute(
            one_shot_submit,
            store=store,
            token=token,
            page=page,
            journal_path=journal_path,
            review_hash=review_hash,
        )
    assert page.click_count == 1


@pytest.mark.parametrize("gate", ["captcha", "assessment", "email_verification", "identity_verification"])
def test_submit_rejects_mandatory_human_gate_before_authorization_or_click(tmp_path, gate):
    import one_shot_submit

    class NeverConsume:
        def consume(self, **kwargs):
            pytest.fail("authorization must not be consumed")

    journal_path = tmp_path / "page-actions.jsonl"
    page = ExactSubmitPage(journal_path, gates=[gate])

    with pytest.raises(one_shot_submit.SubmitBlockedError, match=gate):
        execute(
            one_shot_submit,
            store=NeverConsume(),
            token="unused",
            page=page,
            journal_path=journal_path,
            review_hash="a" * 64,
        )

    assert page.click_count == 0
    assert not journal_path.exists()


def test_submit_rejects_unapproved_maango_or_non_exact_control(tmp_path):
    import one_shot_submit

    class NeverConsume:
        def consume(self, **kwargs):
            pytest.fail("authorization must not be consumed")

    journal_path = tmp_path / "page-actions.jsonl"
    maango_page = ExactSubmitPage(journal_path, maango=True)
    with pytest.raises(one_shot_submit.SubmitBlockedError, match="MAANGO approval"):
        execute(
            one_shot_submit,
            store=NeverConsume(),
            token="unused",
            page=maango_page,
            journal_path=journal_path,
            review_hash="a" * 64,
        )

    hidden_page = ExactSubmitPage(journal_path)
    hidden_page.inspect_submit_control = lambda selector: {
        "selector": selector,
        "target_id": "page-42",
        "url": PAGE_URL,
        "visible": False,
        "enabled": True,
        "unique": True,
        "role": "button",
    }
    with pytest.raises(one_shot_submit.SubmitBlockedError, match="visible, enabled, unique button"):
        execute(
            one_shot_submit,
            store=NeverConsume(),
            token="unused",
            page=hidden_page,
            journal_path=journal_path,
            review_hash="a" * 64,
        )
