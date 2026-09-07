"""Durable confirmed-application outbox; Sheets is explicitly opt-in only."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Protocol


class TrackerAdapter(Protocol):
    def append(self, *, transaction_id: str, payload: dict, payload_sha256: str) -> None: ...

    def read_back(self, *, transaction_id: str) -> dict | None: ...


class DiscordAdapter(Protocol):
    # Legacy fixture adapters may return None; live adapters return the external
    # receipt ID so the coordinator can persist it before attempting read-back.
    def send(self, *, transaction_id: str, message: str, message_sha256: str) -> dict | None: ...

    def read_back(self, *, transaction_id: str, receipt_id: str | None = None) -> dict | None: ...


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
                "SELECT * FROM post_submit_transactions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None and connection.execute("SELECT 1 FROM sqlite_master WHERE name = ?",
                                                   ("post_submit_job_aliases",)).fetchone():
                row = connection.execute(
                    "SELECT t.* FROM post_submit_transactions t JOIN post_submit_job_aliases a "
                    "ON a.transaction_id = t.transaction_id WHERE a.job_id = ?", (job_id,)
                ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error:
        return {"status": "invalid", "tracker": "unknown", "discord": "unknown"}
    if row is None:
        return {"status": "not_started", "tracker": "not_started", "discord": "not_started"}
    tracker_requested = row["tracker_requested"] if "tracker_requested" in row.keys() else 1
    tracker_state = (
        "not_requested" if not tracker_requested else
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
        if row["tracker_verified"] == 1 or not tracker_requested
        else "not_started"
    )
    return {
        "status": "complete" if row["discord_verified"] == 1 else "partial",
        "application_state": "portal_confirmed",
        "portal_confirmed": True,
        "notification_state": "delivered" if row["discord_verified"] == 1 else "pending",
        "tracker": tracker_state,
        "discord": discord_state,
    }


def _validate_portal(portal: dict) -> None:
    readback = portal.get("portal_readback", {})
    evidence = portal.get("evidence", {})
    confirmation = portal.get("confirmation", {})
    identity = portal.get("identity", {})
    reader = portal.get("reader", {})
    proof = evidence.get("provenance", {}) if isinstance(evidence, dict) else {}
    binding = proof.get("binding", {}) if isinstance(proof, dict) else {}
    guest = False
    if all(isinstance(x, dict) for x in (readback, evidence, confirmation, identity, reader, proof, binding)):
        from greenhouse_guest_confirmation import is_permitted_confirmation_url
        guest = (
            portal.get("platform") == "greenhouse"
            and portal.get("confirmation_basis") == "greenhouse_guest_one_shot"
            and portal.get("replay_allowed") is False
            and readback.get("applicable") is False
            and readback.get("matched_application_count") == 0
            and reader.get("verified") is True and reader.get("mode") == "guest_one_shot"
            and proof.get("source") == "one_shot_same_tab_observation"
            and binding.get("requisition") == identity.get("requisition")
            and type(binding.get("job_id")) is int and binding["job_id"] > 0
            and isinstance(binding.get("target_id"), str) and bool(binding["target_id"])
            and all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) for v in (
                binding.get("review_evidence_sha256"), proof.get("intent_sha256"),
                proof.get("before_html_sha256"), proof.get("after_html_sha256"),
                proof.get("after_body_text_sha256")))
            and proof.get("before_html_sha256") != proof.get("after_html_sha256")
            and proof.get("after_body_text_sha256") == confirmation.get("text_sha256")
            and isinstance(binding.get("page_url"), str) and isinstance(reader.get("tenant"), str)
            and is_permitted_confirmation_url(origin_url=binding["page_url"],
                page_url=confirmation.get("url"), tenant=reader["tenant"])
        )
    account = isinstance(readback, dict) and (
        readback.get("matched_application_count") == 1 and readback.get("state") == "submitted"
        and readback.get("submitted") is True and readback.get("verified") is True)
    if (
        portal.get("portal_confirmed") is not True
        or portal.get("safe_for_post_submit") is not True
        or portal.get("human_required") != []
        or not (guest or account)
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


def _durable_guest_fields(portal: dict) -> dict:
    """Retain only the validated, non-content guest proof needed after restart."""
    if portal.get('confirmation_basis') != 'greenhouse_guest_one_shot':
        return {}
    proof=portal['evidence']['provenance']
    return {
        'confirmation_basis':portal['confirmation_basis'], 'replay_allowed':False,
        'reader':{k:portal['reader'][k] for k in ('platform','tenant','verified','mode')},
        'portal_readback':{k:portal['portal_readback'][k] for k in
            ('matched_application_count','state','submitted','verified','applicable')},
        'evidence':{'sanitized':True,'provenance':{
            **{k:proof[k] for k in ('source','intent_sha256','before_html_sha256','after_html_sha256','after_body_text_sha256')},
            'binding':{k:proof['binding'][k] for k in ('job_id','target_id','page_url','requisition','review_evidence_sha256')},
        }},
    }


class PostSubmitTransactionCoordinator:
    """Coordinate downstream effects without exposing any submit operation."""

    def __init__(
        self,
        *,
        state_path: Path | str,
        tracker: TrackerAdapter | None = None,
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

            columns = {row[1] for row in connection.execute("PRAGMA table_info(post_submit_transactions)")}
            if "tracker_requested" not in columns:
                connection.execute("ALTER TABLE post_submit_transactions ADD COLUMN "
                                   "tracker_requested INTEGER NOT NULL DEFAULT 1")

            for name in ("discord_message", "discord_nonce", "portal_evidence_json", "identity_sha256"):
                if name not in columns:
                    connection.execute(f"ALTER TABLE post_submit_transactions ADD COLUMN {name} TEXT")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS post_submit_identity "
                               "ON post_submit_transactions(identity_sha256)")
            connection.execute("CREATE TABLE IF NOT EXISTS post_submit_job_aliases "
                               "(job_id INTEGER PRIMARY KEY, transaction_id TEXT NOT NULL)")

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
        discord_message: str,
        portal_evidence_json: str,
    ) -> sqlite3.Row:
        # transaction_id is the immutable identity key for new rows. Preserve
        # old external markers/nonces when migrating a previously attempted row.
        identity_hash = transaction_id
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM post_submit_transactions WHERE job_id = ? OR identity_sha256 = ? "
                "OR transaction_id IN (SELECT transaction_id FROM post_submit_job_aliases WHERE job_id = ?)",
                (job_id, identity_hash, job_id),
            ).fetchall()
            if len(rows) > 1:
                raise ValueError("immutable job identity conflicts with existing transactions")
            if rows:
                row = rows[0]
                if row["identity_sha256"] not in (None, identity_hash):
                    raise ValueError("immutable job identity drifted")
                if (row["identity_sha256"] is None and row["transaction_id"] != identity_hash
                        and row["portal_sha256"] != portal_sha256):
                    raise ValueError("legacy identity migration requires original portal evidence")
                if (row["tracker_payload_sha256"] != tracker_payload_sha256
                        or row["discord_message_sha256"] != discord_message_sha256
                        or row["tracker_requested"] != int(self.tracker is not None)):
                    raise ValueError("post-submit tracker or Discord evidence drifted")
                transaction_id = row["transaction_id"]
                connection.execute(
                    "UPDATE post_submit_transactions SET identity_sha256 = ?, "
                    "discord_message = COALESCE(discord_message, ?), "
                    "discord_nonce = COALESCE(discord_nonce, ?), "
                    "portal_evidence_json = COALESCE(portal_evidence_json, ?) WHERE transaction_id = ?",
                    (identity_hash, discord_message, transaction_id[:25], portal_evidence_json, transaction_id),
                )
            else:
                connection.execute(
                    "INSERT INTO post_submit_transactions (transaction_id, job_id, portal_sha256, "
                    "tracker_payload_sha256, discord_message_sha256, tracker_requested, "
                    "discord_message, discord_nonce, portal_evidence_json, identity_sha256) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (transaction_id, job_id, portal_sha256, tracker_payload_sha256, discord_message_sha256,
                     int(self.tracker is not None), discord_message, transaction_id[:25],
                     portal_evidence_json, identity_hash),
                )
            connection.execute("INSERT OR IGNORE INTO post_submit_job_aliases VALUES (?, ?)",
                               (job_id, transaction_id))
            row = connection.execute("SELECT * FROM post_submit_transactions WHERE transaction_id = ?",
                                     (transaction_id,)).fetchone()
        assert row is not None
        return row
    def _row(self, transaction_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM post_submit_transactions WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
        assert row is not None
        return row

    def _read_discord(self, transaction_id: str) -> dict | None:
        receipt_id = self._row(transaction_id)["discord_receipt_id"]
        if receipt_id:
            return self.discord.read_back(transaction_id=transaction_id, receipt_id=receipt_id)
        return self.discord.read_back(transaction_id=transaction_id)

    def _save_discord_receipt(self, transaction_id: str, receipt: object) -> None:
        receipt_id = receipt.get("receipt_id") if isinstance(receipt, dict) else None
        if isinstance(receipt_id, str) and receipt_id:
            with self._connect() as connection:
                connection.execute("UPDATE post_submit_transactions SET discord_receipt_id = ? "
                                   "WHERE transaction_id = ? AND discord_verified = 0",
                                   (receipt_id, transaction_id))

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
            and isinstance(readback.get("receipt_id"), str)
            and bool(readback["receipt_id"])
        )

    def _partial(self, transaction_id: str, *, stage: str) -> dict[str, object]:
        row = self._row(transaction_id)
        return {
            "status": "partial",
            "portal_confirmed": True,
            "application_state": "portal_confirmed",
            "notification_state": "delivered" if row["discord_verified"] == 1 else "pending",
            "tracker": {"status": "not_requested" if not row["tracker_requested"] else
                        "complete" if row["tracker_verified"] else "pending"},
            "stage": stage,
            "transaction_id": transaction_id,
            "next_action": ("deliver_notification" if stage == "notification_pending" else
                            "read_back_without_replaying_side_effect"),
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
            "application_state": "portal_confirmed",
            "notification_state": "delivered",
            "identity": {
                key: portal["identity"][key]
                for key in ("company", "role", "requisition")
            },
            "confirmation": {
                key: portal["confirmation"].get(key)
                for key in ("url", "reference_id", "text_sha256")
            },
            "tracker": {
                "status": "complete" if row["tracker_requested"] else "not_requested",
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

    def resume_notification(self, *, job_id: int) -> dict[str, object]:
        """Resume the default no-Sheets outbox using only its durable payload."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT t.* FROM post_submit_transactions t JOIN post_submit_job_aliases a "
                "ON a.transaction_id = t.transaction_id WHERE a.job_id = ?", (job_id,)
            ).fetchone()
        if row is None or not row["portal_evidence_json"]:
            raise ValueError("durable notification payload is unavailable")
        if row["tracker_requested"] or self.tracker is not None:
            raise ValueError("explicit tracker transactions require their original payload")
        return self.run(job_id=job_id, portal_evidence=json.loads(row["portal_evidence_json"]),
                        discord_message=row["discord_message"])

    def run(
        self,
        *,
        job_id: int,
        portal_evidence: dict,
        tracker_payload: dict | None = None,
        discord_message: str,
        deliver: bool = True,
    ) -> dict[str, object]:
        _validate_portal(portal_evidence)
        if not isinstance(job_id, int) or job_id <= 0:
            raise ValueError("positive job ID is required")
        if ((self.tracker is not None and not isinstance(tracker_payload, dict))
                or not isinstance(discord_message, str) or not discord_message):
            raise ValueError("tracker payload and Discord message are required")
        portal_hash = _json_hash(portal_evidence)
        tracker_hash = _json_hash(tracker_payload if self.tracker is not None else None)
        discord_hash = _text_hash(discord_message)
        transaction_id = _json_hash({
            "platform": portal_evidence["platform"],
            "company": portal_evidence["identity"]["company"],
            "requisition": portal_evidence["identity"]["requisition"],
        })
        row = self._initialize(
            job_id=job_id,
            transaction_id=transaction_id,
            portal_sha256=portal_hash,
            tracker_payload_sha256=tracker_hash,
            discord_message_sha256=discord_hash,
            discord_message=discord_message,
            portal_evidence_json=json.dumps({
                "platform": portal_evidence["platform"],
                "portal_confirmed": True, "safe_for_post_submit": True, "human_required": [],
                "identity": {key: portal_evidence["identity"][key]
                             for key in ("company", "role", "requisition")},
                "confirmation": {key: portal_evidence["confirmation"].get(key)
                                 for key in ("url", "reference_id", "submitted", "text_sha256")},
                "portal_readback": {key: portal_evidence["portal_readback"][key]
                                    for key in ("matched_application_count", "state", "submitted", "verified")},
                "evidence": {"sanitized": True},
                **_durable_guest_fields(portal_evidence),
            }),
        )
        transaction_id = row["transaction_id"]
        if row["discord_verified"] == 1:
            return self._final(row=row, portal=portal_evidence)
        if not deliver:
            return self._partial(transaction_id, stage="notification_pending")

        if self.tracker is not None and row["tracker_verified"] != 1:
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
        if self.tracker is not None and row["tracker_verified"] != 1:
            return self._partial(transaction_id, stage="tracker_readback_pending")
        if row["discord_verified"] != 1:
            try:
                discord_readback = self._read_discord(transaction_id)
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
            elif discord_readback is not None:
                return self._partial(transaction_id, stage="discord_readback_pending")
            elif row["discord_attempted"] == 0 and self._claim(transaction_id, "discord_attempted"):
                try:
                    receipt = self.discord.send(
                        transaction_id=transaction_id,
                        message=discord_message,
                        message_sha256=discord_hash,
                    )
                    self._save_discord_receipt(transaction_id, receipt)
                    discord_readback = self._read_discord(transaction_id)
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
