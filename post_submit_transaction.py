"""Resumable portal → tracker/read-back → Discord/read-back transaction."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Protocol


class TrackerAdapter(Protocol):
    def append(self, *, transaction_id: str, payload: dict, payload_sha256: str) -> None: ...

    def read_back(self, *, transaction_id: str) -> dict | None: ...


class DiscordAdapter(Protocol):
    def send(self, *, transaction_id: str, message: str, message_sha256: str) -> None: ...

    def read_back(self, *, transaction_id: str) -> dict | None: ...


def _json_hash(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def inspect_transaction_state(state_path: Path | str, *, job_id: int) -> dict[str, object]:
    """Read durable downstream flags without constructing or calling adapters."""
    path = Path(state_path)
    if not path.is_file():
        return {"status": "not_started", "tracker": "not_started", "discord": "not_started"}
    try:
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT tracker_attempted, tracker_verified, discord_attempted, "
                "discord_verified FROM post_submit_transactions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return {"status": "invalid", "tracker": "unknown", "discord": "unknown"}
    if row is None:
        return {"status": "not_started", "tracker": "not_started", "discord": "not_started"}
    tracker_state = (
        "complete"
        if row["tracker_verified"] == 1
        else "readback_pending"
        if row["tracker_attempted"] == 1
        else "not_started"
    )
    discord_state = (
        "complete"
        if row["discord_verified"] == 1
        else "readback_pending"
        if row["discord_attempted"] == 1
        else "ready"
        if row["tracker_verified"] == 1
        else "not_started"
    )
    return {
        "status": "complete" if row["discord_verified"] == 1 else "partial",
        "tracker": tracker_state,
        "discord": discord_state,
    }


def _validate_portal(portal: dict) -> None:
    readback = portal.get("portal_readback", {})
    evidence = portal.get("evidence", {})
    confirmation = portal.get("confirmation", {})
    identity = portal.get("identity", {})
    if (
        portal.get("portal_confirmed") is not True
        or portal.get("safe_for_post_submit") is not True
        or portal.get("human_required") != []
        or not isinstance(readback, dict)
        or readback.get("matched_application_count") != 1
        or readback.get("state") != "submitted"
        or readback.get("submitted") is not True
        or readback.get("verified") is not True
        or not isinstance(evidence, dict)
        or evidence.get("sanitized") is not True
        or not isinstance(confirmation, dict)
        or confirmation.get("submitted") is not True
        or not isinstance(confirmation.get("text_sha256"), str)
        or len(confirmation["text_sha256"]) != 64
        or not isinstance(identity, dict)
        or not all(
            isinstance(identity.get(key), str) and identity[key]
            for key in ("company", "role", "requisition")
        )
    ):
        raise ValueError("verified portal confirmation is required before post-submit delivery")


class PostSubmitTransactionCoordinator:
    """Coordinate downstream effects without exposing any submit operation."""

    def __init__(
        self,
        *,
        state_path: Path | str,
        tracker: TrackerAdapter,
        discord: DiscordAdapter,
    ) -> None:
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.tracker = tracker
        self.discord = discord
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS post_submit_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    job_id INTEGER NOT NULL UNIQUE,
                    portal_sha256 TEXT NOT NULL,
                    tracker_payload_sha256 TEXT NOT NULL,
                    discord_message_sha256 TEXT NOT NULL,
                    tracker_attempted INTEGER NOT NULL DEFAULT 0,
                    tracker_verified INTEGER NOT NULL DEFAULT 0,
                    tracker_receipt_id TEXT,
                    discord_attempted INTEGER NOT NULL DEFAULT 0,
                    discord_verified INTEGER NOT NULL DEFAULT 0,
                    discord_receipt_id TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.state_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(
        self,
        *,
        job_id: int,
        transaction_id: str,
        portal_sha256: str,
        tracker_payload_sha256: str,
        discord_message_sha256: str,
    ) -> sqlite3.Row:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO post_submit_transactions (
                    transaction_id, job_id, portal_sha256,
                    tracker_payload_sha256, discord_message_sha256
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    job_id,
                    portal_sha256,
                    tracker_payload_sha256,
                    discord_message_sha256,
                ),
            )
            row = connection.execute(
                "SELECT * FROM post_submit_transactions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        assert row is not None
        if (
            row["transaction_id"] != transaction_id
            or row["portal_sha256"] != portal_sha256
            or row["tracker_payload_sha256"] != tracker_payload_sha256
            or row["discord_message_sha256"] != discord_message_sha256
        ):
            raise ValueError("post-submit portal, tracker, or Discord evidence drifted")
        return row

    def _row(self, transaction_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM post_submit_transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        assert row is not None
        return row

    def _claim(self, transaction_id: str, column: str) -> bool:
        if column not in {"tracker_attempted", "discord_attempted"}:
            raise ValueError("invalid transaction claim")
        with self._connect() as connection:
            updated = connection.execute(
                f"UPDATE post_submit_transactions SET {column} = 1 "
                f"WHERE transaction_id = ? AND {column} = 0",
                (transaction_id,),
            )
        return updated.rowcount == 1

    def _mark_verified(
        self, transaction_id: str, *, stage: str, receipt_id: object
    ) -> None:
        if stage not in {"tracker", "discord"}:
            raise ValueError("invalid verified transaction stage")
        safe_receipt = receipt_id if isinstance(receipt_id, str) else ""
        with self._connect() as connection:
            connection.execute(
                f"UPDATE post_submit_transactions "
                f"SET {stage}_verified = 1, {stage}_receipt_id = ? "
                "WHERE transaction_id = ?",
                (safe_receipt, transaction_id),
            )

    @staticmethod
    def _tracker_verified(readback: object, *, transaction_id: str, payload_hash: str) -> bool:
        return (
            isinstance(readback, dict)
            and readback.get("verified") is True
            and readback.get("transaction_id") == transaction_id
            and readback.get("payload_sha256") == payload_hash
        )

    @staticmethod
    def _discord_verified(readback: object, *, transaction_id: str, message_hash: str) -> bool:
        return (
            isinstance(readback, dict)
            and readback.get("verified") is True
            and readback.get("transaction_id") == transaction_id
            and readback.get("message_sha256") == message_hash
        )

    @staticmethod
    def _partial(transaction_id: str, *, stage: str) -> dict[str, object]:
        return {
            "status": "partial",
            "stage": stage,
            "transaction_id": transaction_id,
            "next_action": "read_back_without_replaying_side_effect",
            "submit_replayed": False,
            "sanitized": True,
        }

    @staticmethod
    def _final(
        *,
        row: sqlite3.Row,
        portal: dict,
    ) -> dict[str, object]:
        return {
            "status": "complete",
            "transaction_id": row["transaction_id"],
            "job_id": row["job_id"],
            "portal_confirmed": True,
            "identity": {
                key: portal["identity"][key]
                for key in ("company", "role", "requisition")
            },
            "confirmation": {
                key: portal["confirmation"].get(key)
                for key in ("url", "reference_id", "text_sha256")
            },
            "tracker": {
                "payload_sha256": row["tracker_payload_sha256"],
                "receipt_id": row["tracker_receipt_id"] or "",
                "readback_verified": row["tracker_verified"] == 1,
            },
            "discord": {
                "message_sha256": row["discord_message_sha256"],
                "receipt_id": row["discord_receipt_id"] or "",
                "readback_verified": row["discord_verified"] == 1,
            },
            "submit_replayed": False,
            "sanitized": True,
        }

    def run(
        self,
        *,
        job_id: int,
        portal_evidence: dict,
        tracker_payload: dict,
        discord_message: str,
    ) -> dict[str, object]:
        _validate_portal(portal_evidence)
        if not isinstance(job_id, int) or job_id <= 0:
            raise ValueError("positive job ID is required")
        if not isinstance(tracker_payload, dict) or not isinstance(discord_message, str) or not discord_message:
            raise ValueError("tracker payload and Discord message are required")
        portal_hash = _json_hash(portal_evidence)
        tracker_hash = _json_hash(tracker_payload)
        discord_hash = _text_hash(discord_message)
        transaction_id = _json_hash({
            "job_id": job_id,
            "platform": portal_evidence["platform"],
            "identity": portal_evidence["identity"],
            "confirmation_sha256": portal_evidence["confirmation"]["text_sha256"],
        })
        row = self._initialize(
            job_id=job_id,
            transaction_id=transaction_id,
            portal_sha256=portal_hash,
            tracker_payload_sha256=tracker_hash,
            discord_message_sha256=discord_hash,
        )
        if row["discord_verified"] == 1:
            return self._final(row=row, portal=portal_evidence)

        if row["tracker_verified"] != 1:
            try:
                tracker_readback = self.tracker.read_back(transaction_id=transaction_id)
            except Exception:
                return self._partial(transaction_id, stage="tracker_readback_pending")
            if self._tracker_verified(
                tracker_readback,
                transaction_id=transaction_id,
                payload_hash=tracker_hash,
            ):
                self._mark_verified(
                    transaction_id,
                    stage="tracker",
                    receipt_id=tracker_readback.get("receipt_id"),
                )
            elif row["tracker_attempted"] == 0 and self._claim(transaction_id, "tracker_attempted"):
                try:
                    self.tracker.append(
                        transaction_id=transaction_id,
                        payload=tracker_payload,
                        payload_sha256=tracker_hash,
                    )
                    tracker_readback = self.tracker.read_back(transaction_id=transaction_id)
                except Exception:
                    return self._partial(transaction_id, stage="tracker_readback_pending")
                if self._tracker_verified(
                    tracker_readback,
                    transaction_id=transaction_id,
                    payload_hash=tracker_hash,
                ):
                    self._mark_verified(
                        transaction_id,
                        stage="tracker",
                        receipt_id=tracker_readback.get("receipt_id"),
                    )
                else:
                    return self._partial(transaction_id, stage="tracker_readback_pending")
            else:
                return self._partial(transaction_id, stage="tracker_readback_pending")

        row = self._row(transaction_id)
        if row["tracker_verified"] != 1:
            return self._partial(transaction_id, stage="tracker_readback_pending")
        if row["discord_verified"] != 1:
            try:
                discord_readback = self.discord.read_back(transaction_id=transaction_id)
            except Exception:
                return self._partial(transaction_id, stage="discord_readback_pending")
            if self._discord_verified(
                discord_readback,
                transaction_id=transaction_id,
                message_hash=discord_hash,
            ):
                self._mark_verified(
                    transaction_id,
                    stage="discord",
                    receipt_id=discord_readback.get("receipt_id"),
                )
            elif row["discord_attempted"] == 0 and self._claim(transaction_id, "discord_attempted"):
                try:
                    self.discord.send(
                        transaction_id=transaction_id,
                        message=discord_message,
                        message_sha256=discord_hash,
                    )
                    discord_readback = self.discord.read_back(transaction_id=transaction_id)
                except Exception:
                    return self._partial(transaction_id, stage="discord_readback_pending")
                if self._discord_verified(
                    discord_readback,
                    transaction_id=transaction_id,
                    message_hash=discord_hash,
                ):
                    self._mark_verified(
                        transaction_id,
                        stage="discord",
                        receipt_id=discord_readback.get("receipt_id"),
                    )
                else:
                    return self._partial(transaction_id, stage="discord_readback_pending")
            else:
                return self._partial(transaction_id, stage="discord_readback_pending")

        return self._final(row=self._row(transaction_id), portal=portal_evidence)
