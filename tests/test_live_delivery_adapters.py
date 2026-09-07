from __future__ import annotations

import hashlib
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


def test_discord_rest_uses_injected_transport_for_exact_get_and_nonce_send():
    import json
    import live_delivery_adapters as adapters
    calls = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"id":"message-1"}'
    def opener(request, *, timeout):
        calls.append(request)
        assert timeout == 30
        return Response()
    client = adapters.DiscordRESTClient(token_provider=lambda: "offline-fixture", opener=opener)
    assert client.get_message_authenticated("channel-1", "message-1") == {"id": "message-1"}
    assert calls[0].full_url.endswith("/channels/channel-1/messages/message-1")
    client.send_message_authenticated("channel-1", content="Submitted", nonce="stable-nonce")
    assert json.loads(calls[1].data) == {"content": "Submitted", "nonce": "stable-nonce",
                                       "enforce_nonce": True, "allowed_mentions": {"parse": []}}


def test_discord_rejects_incorrect_message_hash_before_any_external_call():
    import live_delivery_adapters as adapters
    calls = []
    class Client:
        def list_messages_authenticated(self, *args, **kwargs):
            calls.append("read")
            return []
        def send_message_authenticated(self, *args, **kwargs):
            calls.append("send")
            return {"id": "message-1"}
    adapter = adapters.DiscordTransactionAdapter(commit_mode="commit_external", channel_id="channel-1", client=Client())
    with pytest.raises(ValueError, match="message hash"):
        adapter.send(transaction_id="transaction-1", message="Submitted", message_sha256="a" * 64)
    assert calls == []


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


@pytest.mark.parametrize("mutation", ["body", "id", "channel", "nonce", "suffix", "duplicate"])
def test_discord_readback_requires_exact_content_and_receipt(mutation):
    import hashlib
    import live_delivery_adapters as adapters
    message = "Application submitted"
    digest = hashlib.sha256(message.encode()).hexdigest()
    content = f"{message}\njob-agent-transaction=transaction-1;message_sha256={digest}"
    item = {"id": "message-1", "content": content, "nonce": "transaction-1", "channel_id": "channel-1"}
    if mutation == "body": item["content"] = content.replace(message, "Application FAILED")
    if mutation == "id": item["id"] = ""
    if mutation == "channel": item["channel_id"] = "another-channel"
    if mutation == "nonce": item["nonce"] = "another-transaction"
    if mutation == "suffix": item["content"] += "modified"
    class Client:
        def list_messages_authenticated(self, channel_id, *, limit):
            return [item, {**item, "id": "message-2"}] if mutation == "duplicate" else [item]
    adapter = adapters.DiscordTransactionAdapter(commit_mode="commit_external", channel_id="channel-1", client=Client())
    with pytest.raises(ValueError, match="exact read-back conflict"):
        adapter.read_back(transaction_id="transaction-1")


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
        message_sha256=hashlib.sha256(b"Sanitized delivery").hexdigest(),
    )
    adapter.send(
        transaction_id="transaction-1",
        message="Sanitized delivery",
        message_sha256=hashlib.sha256(b"Sanitized delivery").hexdigest(),
    )

    assert client.send_count == 1
    assert adapter.read_back(transaction_id="transaction-1") == {
        "verified": True,
        "transaction_id": "transaction-1",
        "message_sha256": hashlib.sha256(b"Sanitized delivery").hexdigest(),
        "receipt_id": "message-1",
        "readback_source": "authenticated_discord_api",
    }
