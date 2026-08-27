from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


TRACKER_PAYLOAD = {
    "company": "Sanitized Example",
    "status": "Submitted - Pending Response",
    "role": "Software Engineer Intern",
    "salary": "",
    "date_submitted": "2026-08-27",
    "job_url": "https://example.test/REQ-123",
    "rejection_reason": "N/A",
    "notes": "Verified portal confirmation",
}


def test_commit_gated_tracker_adapter_uses_idempotency_marker_and_authenticated_readback():
    import live_delivery_adapters
    import tracker

    class Backend:
        def __init__(self):
            self.rows = []
            self.append_count = 0

        def fetch_rows_authenticated(self):
            return list(self.rows)

        def append_verified(self, values):
            self.append_count += 1
            self.rows.append(dict(zip(tracker.HEADERS, values)))
            return {"verified": True}

    blocked_backend = Backend()
    blocked = live_delivery_adapters.GoogleSheetsTransactionAdapter(
        commit_mode="disabled", backend=blocked_backend
    )
    with pytest.raises(PermissionError, match="explicit external commit mode"):
        blocked.append(
            transaction_id="transaction-1",
            payload=TRACKER_PAYLOAD,
            payload_sha256="a" * 64,
        )
    assert blocked_backend.append_count == 0

    backend = Backend()
    adapter = live_delivery_adapters.GoogleSheetsTransactionAdapter(
        commit_mode="commit_external", backend=backend
    )
    adapter.append(
        transaction_id="transaction-1",
        payload=TRACKER_PAYLOAD,
        payload_sha256="a" * 64,
    )
    adapter.append(
        transaction_id="transaction-1",
        payload=TRACKER_PAYLOAD,
        payload_sha256="a" * 64,
    )

    assert backend.append_count == 1
    assert adapter.read_back(transaction_id="transaction-1") == {
        "verified": True,
        "transaction_id": "transaction-1",
        "payload_sha256": "a" * 64,
        "receipt_id": "google-sheets:transaction-1",
        "readback_source": "authenticated_google_sheets_api",
    }


def test_commit_gated_discord_adapter_uses_idempotency_marker_and_authenticated_readback():
    import live_delivery_adapters

    class Client:
        def __init__(self):
            self.messages = []
            self.send_count = 0

        def list_messages_authenticated(self, channel_id, *, limit):
            assert channel_id == "channel-1"
            assert limit == 100
            return list(self.messages)

        def send_message_authenticated(self, channel_id, *, content, nonce):
            self.send_count += 1
            self.messages.append({"id": "message-1", "content": content, "nonce": nonce})
            return self.messages[-1]

    client = Client()
    adapter = live_delivery_adapters.DiscordTransactionAdapter(
        commit_mode="commit_external", channel_id="channel-1", client=client
    )
    adapter.send(
        transaction_id="transaction-1",
        message="Sanitized delivery",
        message_sha256="b" * 64,
    )
    adapter.send(
        transaction_id="transaction-1",
        message="Sanitized delivery",
        message_sha256="b" * 64,
    )

    assert client.send_count == 1
    assert adapter.read_back(transaction_id="transaction-1") == {
        "verified": True,
        "transaction_id": "transaction-1",
        "message_sha256": "b" * 64,
        "receipt_id": "message-1",
        "readback_source": "authenticated_discord_api",
    }
