"""Commit-gated external tracker and Discord transaction adapters.

The adapters never obtain authorization from their payload.  Every external
method requires the constructor capability ``commit_external`` and confirms an
idempotency marker through an authenticated read-back API.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Callable, Protocol

import tracker


COMMIT_EXTERNAL = "commit_external"
TRACKER_KEYS = (
    "company",
    "status",
    "role",
    "salary",
    "date_submitted",
    "job_url",
    "rejection_reason",
    "notes",
)
MARKER_PATTERN = re.compile(
    r"job-agent-transaction=([A-Za-z0-9_-]{1,128});(?:payload|message)_sha256=([0-9a-f]{64})"
)


class SheetsBackend(Protocol):
    def fetch_rows_authenticated(self) -> list[dict[str, str]]: ...

    def append_verified(self, values: list[str]) -> dict: ...


class DiscordClient(Protocol):
    def list_messages_authenticated(self, channel_id: str, *, limit: int) -> list[dict]: ...

    def send_message_authenticated(
        self, channel_id: str, *, content: str, nonce: str
    ) -> dict: ...


def _require_commit(mode: str) -> None:
    if mode != COMMIT_EXTERNAL:
        raise PermissionError("explicit external commit mode is required")


def _marker(*, transaction_id: str, digest: str, kind: str) -> str:
    if (
        not isinstance(transaction_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", transaction_id) is None
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        or kind not in {"payload", "message"}
    ):
        raise ValueError("valid idempotency transaction and digest are required")
    return f"job-agent-transaction={transaction_id};{kind}_sha256={digest}"


class _TrackerBackend:
    def fetch_rows_authenticated(self) -> list[dict[str, str]]:
        return tracker.fetch_rows_via_api()

    def append_verified(self, values: list[str]) -> dict:
        return tracker.append_verified(values)


class GoogleSheetsTransactionAdapter:
    """Append one marked tracker row and verify it through authenticated Sheets."""

    def __init__(self, *, commit_mode: str, backend: SheetsBackend | None = None) -> None:
        self.commit_mode = commit_mode
        self.backend = backend or _TrackerBackend()

    def read_back(self, *, transaction_id: str) -> dict | None:
        _require_commit(self.commit_mode)
        prefix = f"job-agent-transaction={transaction_id};payload_sha256="
        for row in self.backend.fetch_rows_authenticated():
            notes = row.get("Notes", "") if isinstance(row, dict) else ""
            if prefix not in notes:
                continue
            match = MARKER_PATTERN.search(notes)
            if match is None or match.group(1) != transaction_id:
                continue
            return {
                "verified": True,
                "transaction_id": transaction_id,
                "payload_sha256": match.group(2),
                "receipt_id": f"google-sheets:{transaction_id}",
                "readback_source": "authenticated_google_sheets_api",
            }
        return None

    def append(self, *, transaction_id: str, payload: dict, payload_sha256: str) -> None:
        _require_commit(self.commit_mode)
        if not isinstance(payload, dict) or set(payload) != set(TRACKER_KEYS):
            raise ValueError("closed tracker transaction payload is required")
        if not all(isinstance(payload[key], str) for key in TRACKER_KEYS):
            raise ValueError("tracker transaction values must be strings")
        marker = _marker(
            transaction_id=transaction_id, digest=payload_sha256, kind="payload"
        )
        existing = self.read_back(transaction_id=transaction_id)
        if existing is not None:
            if existing.get("payload_sha256") != payload_sha256:
                raise ValueError("tracker idempotency key exists with different payload")
            return
        values = [payload[key] for key in TRACKER_KEYS]
        values[-1] = f"{values[-1]} | {marker}" if values[-1] else marker
        self.backend.append_verified(values)


class DiscordRESTClient:
    """Minimal authenticated Discord API client with runtime-only token supply."""

    def __init__(
        self,
        *,
        token_provider: Callable[[], str],
        base_url: str = "https://discord.com/api/v10",
    ) -> None:
        self.token_provider = token_provider
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict | None = None) -> object:
        token = self.token_provider()
        if not isinstance(token, str) or not token:
            raise PermissionError("Discord runtime credential is unavailable")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bot {token}",
                "Content-Type": "application/json",
                "User-Agent": "job-agent-live-operator/1",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def list_messages_authenticated(self, channel_id: str, *, limit: int) -> list[dict]:
        payload = self._request(
            "GET",
            f"/channels/{urllib.parse.quote(channel_id, safe='')}/messages?limit={limit}",
        )
        if not isinstance(payload, list):
            raise RuntimeError("Discord authenticated read-back was not a list")
        return [item for item in payload if isinstance(item, dict)]

    def send_message_authenticated(
        self, channel_id: str, *, content: str, nonce: str
    ) -> dict:
        payload = self._request(
            "POST",
            f"/channels/{urllib.parse.quote(channel_id, safe='')}/messages",
            {"content": content, "nonce": nonce, "enforce_nonce": True},
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Discord send did not return a message")
        return payload


class DiscordTransactionAdapter:
    """Send one marked message and verify it through authenticated Discord read-back."""

    def __init__(
        self, *, commit_mode: str, channel_id: str, client: DiscordClient
    ) -> None:
        if not isinstance(channel_id, str) or not channel_id:
            raise ValueError("Discord channel ID is required")
        self.commit_mode = commit_mode
        self.channel_id = channel_id
        self.client = client

    def read_back(self, *, transaction_id: str) -> dict | None:
        _require_commit(self.commit_mode)
        prefix = f"job-agent-transaction={transaction_id};message_sha256="
        for item in self.client.list_messages_authenticated(self.channel_id, limit=100):
            content = item.get("content", "")
            if not isinstance(content, str) or prefix not in content:
                continue
            match = MARKER_PATTERN.search(content)
            if match is None or match.group(1) != transaction_id:
                continue
            receipt_id = item.get("id")
            return {
                "verified": True,
                "transaction_id": transaction_id,
                "message_sha256": match.group(2),
                "receipt_id": receipt_id if isinstance(receipt_id, str) else "",
                "readback_source": "authenticated_discord_api",
            }
        return None

    def send(self, *, transaction_id: str, message: str, message_sha256: str) -> None:
        _require_commit(self.commit_mode)
        if not isinstance(message, str) or not message:
            raise ValueError("Discord transaction message is required")
        marker = _marker(
            transaction_id=transaction_id, digest=message_sha256, kind="message"
        )
        existing = self.read_back(transaction_id=transaction_id)
        if existing is not None:
            if existing.get("message_sha256") != message_sha256:
                raise ValueError("Discord idempotency key exists with different message")
            return
        self.client.send_message_authenticated(
            self.channel_id,
            content=f"{message}\n{marker}",
            nonce=transaction_id[:25],
        )
