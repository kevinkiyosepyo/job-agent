from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def portal_evidence() -> dict:
    return {
        "portal_confirmed": True,
        "safe_for_post_submit": True,
        "platform": "greenhouse",
        "identity": {
            "company": "Sanitized Example",
            "role": "Software Engineer Intern",
            "requisition": "REQ-123",
        },
        "confirmation": {
            "url": "https://sanitized.example.test/confirmation/REQ-123",
            "reference_id": "APP-123",
            "submitted": True,
            "text_sha256": "a" * 64,
        },
        "portal_readback": {
            "matched_application_count": 1,
            "state": "submitted",
            "submitted": True,
            "verified": True,
        },
        "human_required": [],
        "evidence": {"sanitized": True, "two_source_reconciliation": True},
    }


class FakeTracker:
    def __init__(self, events: list[str], *, delayed_readback: bool = False):
        self.events = events
        self.delayed_readback = delayed_readback
        self.append_count = 0
        self.read_count = 0
        self.transaction_id = None
        self.payload_sha256 = None

    def append(self, *, transaction_id: str, payload: dict, payload_sha256: str) -> None:
        self.events.append("tracker.append")
        self.append_count += 1
        self.transaction_id = transaction_id
        self.payload_sha256 = payload_sha256

    def read_back(self, *, transaction_id: str) -> dict | None:
        self.events.append("tracker.read_back")
        self.read_count += 1
        if self.transaction_id != transaction_id:
            return None
        if self.delayed_readback and self.read_count < 3:
            return {"verified": False, "transaction_id": transaction_id}
        return {
            "verified": True,
            "transaction_id": transaction_id,
            "payload_sha256": self.payload_sha256,
            "receipt_id": "fixture-sheet-row",
        }


class FakeDiscord:
    def __init__(self, events: list[str], *, delayed_readback: bool = False):
        self.events = events
        self.delayed_readback = delayed_readback
        self.send_count = 0
        self.read_count = 0
        self.transaction_id = None
        self.message_sha256 = None

    def send(self, *, transaction_id: str, message: str, message_sha256: str) -> None:
        self.events.append("discord.send")
        self.send_count += 1
        self.transaction_id = transaction_id
        self.message_sha256 = message_sha256

    def read_back(self, *, transaction_id: str) -> dict | None:
        self.events.append("discord.read_back")
        self.read_count += 1
        if self.transaction_id != transaction_id:
            return None
        if self.delayed_readback and self.read_count < 3:
            return {"verified": False, "transaction_id": transaction_id}
        return {
            "verified": True,
            "transaction_id": transaction_id,
            "message_sha256": self.message_sha256,
            "receipt_id": "fixture-discord-message",
        }


def run(coordinator, portal, tracker_payload=None, discord_message="Fixture application submitted"):
    return coordinator.run(
        job_id=17,
        portal_evidence=portal,
        tracker_payload=tracker_payload or {
            "candidate_name": "Fixture Person",
            "status": "Submitted - Pending Response",
        },
        discord_message=discord_message,
    )


def test_transaction_orders_portal_tracker_readback_discord_readback_and_is_idempotent(tmp_path):
    import post_submit_transaction

    events: list[str] = []
    tracker = FakeTracker(events)
    discord = FakeDiscord(events)
    state_path = tmp_path / "post-submit.db"
    coordinator = post_submit_transaction.PostSubmitTransactionCoordinator(
        state_path=state_path,
        tracker=tracker,
        discord=discord,
    )

    result = run(coordinator, portal_evidence())

    assert events == [
        "tracker.read_back",
        "tracker.append",
        "tracker.read_back",
        "discord.read_back",
        "discord.send",
        "discord.read_back",
    ]
    assert result["status"] == "complete"
    assert result["portal_confirmed"] is True
    assert result["tracker"]["readback_verified"] is True
    assert result["discord"]["readback_verified"] is True
    assert result["submit_replayed"] is False
    assert result["sanitized"] is True
    serialized = json.dumps(result)
    assert "Fixture Person" not in serialized
    assert "Fixture application submitted" not in serialized
    assert b"Fixture Person" not in state_path.read_bytes()

    assert run(coordinator, portal_evidence()) == result
    assert tracker.append_count == 1
    assert discord.send_count == 1
    assert len(events) == 6


def test_tracker_partial_failure_resumes_by_readback_without_duplicate_append_or_early_discord(tmp_path):
    import post_submit_transaction

    events: list[str] = []
    tracker = FakeTracker(events, delayed_readback=True)
    discord = FakeDiscord(events)
    coordinator = post_submit_transaction.PostSubmitTransactionCoordinator(
        state_path=tmp_path / "post-submit.db",
        tracker=tracker,
        discord=discord,
    )

    partial = run(coordinator, portal_evidence())

    assert partial["status"] == "partial"
    assert partial["stage"] == "tracker_readback_pending"
    assert tracker.append_count == 1
    assert discord.send_count == 0

    complete = run(coordinator, portal_evidence())

    assert complete["status"] == "complete"
    assert tracker.append_count == 1
    assert discord.send_count == 1


def test_discord_partial_failure_resumes_by_readback_without_duplicate_send(tmp_path):
    import post_submit_transaction

    events: list[str] = []
    tracker = FakeTracker(events)
    discord = FakeDiscord(events, delayed_readback=True)
    coordinator = post_submit_transaction.PostSubmitTransactionCoordinator(
        state_path=tmp_path / "post-submit.db",
        tracker=tracker,
        discord=discord,
    )

    partial = run(coordinator, portal_evidence())
    complete = run(coordinator, portal_evidence())

    assert partial["stage"] == "discord_readback_pending"
    assert complete["status"] == "complete"
    assert tracker.append_count == 1
    assert discord.send_count == 1


def test_transaction_rejects_unconfirmed_portal_before_tracker_or_discord(tmp_path):
    import post_submit_transaction

    events: list[str] = []
    coordinator = post_submit_transaction.PostSubmitTransactionCoordinator(
        state_path=tmp_path / "post-submit.db",
        tracker=FakeTracker(events),
        discord=FakeDiscord(events),
    )
    portal = portal_evidence()
    portal["portal_confirmed"] = False

    with pytest.raises(ValueError, match="verified portal confirmation"):
        run(coordinator, portal)

    assert events == []
