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


def test_default_transaction_records_confirmation_separate_from_notification(tmp_path):
    import post_submit_transaction as pst
    events = []
    discord = FakeDiscord(events, delayed_readback=True)
    state = tmp_path / "outbox.db"
    coordinator = pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord)
    result = coordinator.run(job_id=17, portal_evidence=portal_evidence(),
                             discord_message="Application submitted")
    assert result["portal_confirmed"] is True
    assert result["application_state"] == "portal_confirmed"
    assert result["notification_state"] == "pending"
    assert result["tracker"]["status"] == "not_requested"
    stored = pst.inspect_transaction_state(state, job_id=17)
    assert stored["application_state"] == "portal_confirmed"
    assert stored["notification_state"] == "pending"
    assert stored["tracker"] == "not_requested"
    restarted = pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord)
    final = restarted.run(job_id=17, portal_evidence=portal_evidence(),
                          discord_message="Application submitted")
    assert final["notification_state"] == "delivered"
    assert discord.send_count == 1
    assert not any(event.startswith("tracker") for event in events)


def test_immutable_job_identity_deduplicates_requeued_job_and_fresh_confirmation(tmp_path):
    import post_submit_transaction as pst
    import sqlite3
    state = tmp_path / "outbox.db"
    discord = FakeDiscord([])
    coordinator = pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord)
    first = coordinator.run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")
    newer_portal = portal_evidence()
    newer_portal["confirmation"]["text_sha256"] = "c" * 64
    newer_portal["identity"]["role"] = "Updated listing display title"
    restarted = pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord)
    second = restarted.run(job_id=99, portal_evidence=newer_portal, discord_message="Submitted")
    assert second["transaction_id"] == first["transaction_id"]
    assert discord.send_count == 1
    assert pst.inspect_transaction_state(state, job_id=99)["notification_state"] == "delivered"
    with sqlite3.connect(state) as db:
        assert db.execute("SELECT COUNT(*) FROM post_submit_transactions").fetchone()[0] == 1


def test_outbox_can_persist_then_deliver_after_restart_without_input_artifacts(tmp_path):
    import post_submit_transaction as pst
    import sqlite3
    state = tmp_path / "outbox.db"
    coordinator = pst.PostSubmitTransactionCoordinator(state_path=state, discord=FakeDiscord([]))
    pending = coordinator.run(job_id=17, portal_evidence=portal_evidence(),
                              discord_message="Durable submitted notice", deliver=False)
    assert pending["notification_state"] == "pending"
    assert pending["portal_confirmed"] is True
    with sqlite3.connect(state) as db:
        row = db.execute("SELECT discord_message, discord_nonce, discord_attempted "
                         "FROM post_submit_transactions").fetchone()
    assert row == ("Durable submitted notice", pending["transaction_id"][:25], 0)
    discord = FakeDiscord([])
    restarted = pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord)
    result = restarted.resume_notification(job_id=17)
    assert result["notification_state"] == "delivered"
    assert discord.send_count == 1


def test_sent_message_id_is_persisted_before_readback_timeout_and_used_after_restart(tmp_path):
    import post_submit_transaction as pst
    from live_delivery_adapters import DiscordTransactionAdapter
    import sqlite3
    class Client:
        sends = 0
        exact_reads = 0
        item = None
        def list_messages_authenticated(self, channel_id, *, limit):
            return []  # Sent message has scrolled beyond the history window.
        def send_message_authenticated(self, channel_id, *, content, nonce):
            self.sends += 1
            self.item = {"id": "message-1", "channel_id": channel_id, "content": content, "nonce": nonce}
            return self.item
        def get_message_authenticated(self, channel_id, message_id):
            assert (channel_id, message_id) == ("channel-1", "message-1")
            self.exact_reads += 1
            if self.exact_reads == 1:
                raise TimeoutError("readback timed out")
            return self.item
    client = Client()
    def coordinator():
        return pst.PostSubmitTransactionCoordinator(state_path=tmp_path / "outbox.db", discord=
            DiscordTransactionAdapter(commit_mode="commit_external", channel_id="channel-1", client=client))
    pending = coordinator().run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")
    assert pending["notification_state"] == "pending"
    with sqlite3.connect(tmp_path / "outbox.db") as db:
        assert db.execute("SELECT discord_receipt_id, discord_verified FROM post_submit_transactions").fetchone() == ("message-1", 0)
    assert coordinator().resume_notification(job_id=17)["notification_state"] == "delivered"
    assert client.sends == 1
    assert client.exact_reads == 2


@pytest.mark.parametrize("field,value", [("receipt_id", ""), ("message_sha256", "wrong"),
                                         ("transaction_id", "wrong"), ("verified", False)])
def test_unverifiable_existing_notification_is_never_treated_as_absent(tmp_path, field, value):
    import post_submit_transaction as pst
    import hashlib
    class Discord(FakeDiscord):
        def read_back(self, *, transaction_id):
            evidence = {"verified": True, "receipt_id": "message-1", "transaction_id": transaction_id,
                        "message_sha256": hashlib.sha256(b"Submitted").hexdigest()}
            evidence[field] = value
            return evidence
    discord = Discord([])
    coordinator = pst.PostSubmitTransactionCoordinator(state_path=tmp_path / "outbox.db", discord=discord)
    result = coordinator.run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")
    assert result["notification_state"] == "pending"
    assert result["portal_confirmed"] is True
    assert discord.send_count == 0


@pytest.mark.parametrize("failure", [TimeoutError, SystemExit])
def test_crash_after_send_unknown_outcome_reconciles_nonce_without_resending(tmp_path, failure):
    import post_submit_transaction as pst
    from live_delivery_adapters import DiscordTransactionAdapter
    class Client:
        sends = 0
        visible = False
        item = None
        def list_messages_authenticated(self, channel_id, *, limit):
            return [self.item] if self.visible else []
        def send_message_authenticated(self, channel_id, *, content, nonce):
            self.sends += 1
            self.item = {"id": "message-1", "content": content, "nonce": nonce, "channel_id": channel_id}
            raise failure("process/ack lost after remote acceptance")
    client = Client()
    def coordinator():
        return pst.PostSubmitTransactionCoordinator(state_path=tmp_path / "outbox.db", discord=
            DiscordTransactionAdapter(commit_mode="commit_external", channel_id="channel-1", client=client))
    if failure is SystemExit:
        with pytest.raises(SystemExit):
            coordinator().run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")
    else:
        assert coordinator().run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")["notification_state"] == "pending"
    assert pst.inspect_transaction_state(tmp_path / "outbox.db", job_id=17)["application_state"] == "portal_confirmed"
    assert coordinator().resume_notification(job_id=17)["notification_state"] == "pending"
    assert client.sends == 1
    client.visible = True
    assert coordinator().resume_notification(job_id=17)["notification_state"] == "delivered"
    assert client.sends == 1


def test_concurrent_notification_workers_claim_one_send(tmp_path):
    import post_submit_transaction as pst
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    state = tmp_path / "outbox.db"
    discord = FakeDiscord([])
    workers = [pst.PostSubmitTransactionCoordinator(state_path=state, discord=discord) for _ in range(2)]
    barrier = Barrier(2)
    def run_worker(worker):
        barrier.wait(timeout=5)
        return worker.run(job_id=17, portal_evidence=portal_evidence(), discord_message="Submitted")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_worker, workers))
    assert all(result["portal_confirmed"] for result in results)
    assert discord.send_count == 1
    assert workers[0].resume_notification(job_id=17)["notification_state"] == "delivered"


def test_legacy_attempted_transaction_migrates_without_changing_external_nonce(tmp_path):
    import post_submit_transaction as pst
    import sqlite3
    import hashlib
    portal = portal_evidence()
    payload = {"status": "Submitted"}
    legacy_id = pst._json_hash({"job_id": 17, "platform": portal["platform"],
        "identity": portal["identity"], "confirmation_sha256": portal["confirmation"]["text_sha256"]})
    state = tmp_path / "outbox.db"
    with sqlite3.connect(state) as db:
        db.execute("CREATE TABLE post_submit_transactions (transaction_id TEXT PRIMARY KEY, job_id INTEGER UNIQUE, "
            "portal_sha256 TEXT, tracker_payload_sha256 TEXT, discord_message_sha256 TEXT, "
            "tracker_attempted INTEGER, tracker_verified INTEGER, tracker_receipt_id TEXT, "
            "discord_attempted INTEGER, discord_verified INTEGER, discord_receipt_id TEXT)")
        db.execute("INSERT INTO post_submit_transactions VALUES (?, 17, ?, ?, ?, 1, 1, 'row-1', 1, 0, NULL)",
                   (legacy_id, pst._json_hash(portal), pst._json_hash(payload), hashlib.sha256(b"Submitted").hexdigest()))
    discord = FakeDiscord([])
    discord.transaction_id = legacy_id
    discord.message_sha256 = hashlib.sha256(b"Submitted").hexdigest()
    coordinator = pst.PostSubmitTransactionCoordinator(state_path=state, tracker=FakeTracker([]), discord=discord)
    result = coordinator.run(job_id=17, portal_evidence=portal, tracker_payload=payload, discord_message="Submitted")
    assert result["notification_state"] == "delivered"
    assert result["transaction_id"] == legacy_id
    assert discord.send_count == 0
    assert coordinator.run(job_id=99, portal_evidence=portal, tracker_payload=payload,
                           discord_message="Submitted")["transaction_id"] == legacy_id


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
