"""Transactional immutable application fence and global rolling-hour pacing.

Authorizations and attempts MUST inhabit one physical database. Reserved and
unknown attempts never expire: a crash suspends all submissions until positive
confirmation, not until the next hourly tick. This module performs no I/O except
SQLite and does not store raw account identity, tokens, or browser evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path


CANONICAL_LEDGER_PATH = Path.home() / "Documents/job-agent/runtime/submission-ledger.sqlite3"


def parse_timestamp(value: str | datetime) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("valid timezone-aware timestamp is required") from None


def application_key(*, job_id: int, requisition: str, account_id: str | None = None,
                    tenant: str | None = None) -> str:
    """Immutable account/tenant/requisition; job ID only for older fixtures."""
    if account_id is None and tenant is None:
        identity = ["legacy-job", job_id]
    elif all(isinstance(value, str) and value for value in (account_id, tenant, requisition)):
        identity = ["application-v1", account_id, tenant, requisition]
    else:
        raise ValueError("complete immutable application identity is required")
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()


def initialize(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS submission_attempts (
            submission_attempt_id TEXT PRIMARY KEY,
            application_key TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('reserved', 'unknown', 'confirmed', 'released')),
            reserved_at TEXT NOT NULL,
            dispatched_at TEXT,
            confirmed_at TEXT,
            released_at TEXT
        )
    """)
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_application_intent
        ON submission_attempts(application_key) WHERE state != 'released'""")
    connection.execute("""CREATE TABLE IF NOT EXISTS submission_imports (
        source_digest TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
        submission_attempt_id TEXT NOT NULL
    )""")


def assert_application_available(connection: sqlite3.Connection, key: str) -> None:
    if connection.execute("SELECT 1 FROM submission_attempts WHERE application_key = ? AND state != 'released'", (key,)).fetchone():
        raise PermissionError("application already has submission intent; no replay")


def _status(connection: sqlite3.Connection, now: str | datetime) -> dict:
    current = parse_timestamp(now)
    pending = connection.execute("""SELECT submission_attempt_id FROM submission_attempts
        WHERE state IN ('reserved', 'unknown') ORDER BY reserved_at LIMIT 1""").fetchone()
    result = {"eligible": True, "reason": "eligible", "pending_attempt_id": None,
              "next_eligible_at": None}
    if pending:
        return {**result, "eligible": False, "reason": "submission_pending", "pending_attempt_id": pending[0]}
    successes = connection.execute("SELECT confirmed_at FROM submission_attempts WHERE state = 'confirmed'").fetchall()
    if successes:
        next_at = max(parse_timestamp(row[0]) for row in successes) + timedelta(hours=1)
        if current < next_at:
            return {**result, "eligible": False, "reason": "hourly_limit", "next_eligible_at": next_at.isoformat()}
    return result


def _transition_time(connection: sqlite3.Connection, attempt_id: str, now: str | datetime) -> str:
    current = parse_timestamp(now)
    row = connection.execute("SELECT reserved_at, dispatched_at FROM submission_attempts WHERE submission_attempt_id = ?",
                             (attempt_id,)).fetchone()
    if row and current < parse_timestamp(row[1] or row[0]):
        raise ValueError("transition timestamp cannot precede submission intent")
    return current.isoformat()


def reserve(connection: sqlite3.Connection, *, key: str, now: str) -> str:
    """Caller owns the IMMEDIATE transaction, including authorization use."""
    assert_application_available(connection, key)
    status = _status(connection, now)
    if not status["eligible"]:
        raise PermissionError("submission pending; inspection only" if status["reason"] == "submission_pending"
                              else "hourly submission limit; no catch-up")
    attempt_id = secrets.token_hex(16)
    connection.execute("""INSERT INTO submission_attempts
        (submission_attempt_id, application_key, state, reserved_at) VALUES (?, ?, 'reserved', ?)""",
        (attempt_id, key, parse_timestamp(now).isoformat()))
    return attempt_id


class SubmissionLedger:
    """Durable state; status is advisory, reserve always rechecks in transaction."""

    def __init__(self, path: Path | str, *, production: bool = False) -> None:
        self.path = Path(path).expanduser().resolve()
        self.production = production
        if production and self.path != CANONICAL_LEDGER_PATH.resolve():
            raise ValueError("production requires the canonical shared submission ledger")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            initialize(connection)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @contextmanager
    def transaction(self):
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def status(self, *, now: str | datetime) -> dict:
        with self.transaction() as connection:
            return _status(connection, now)

    def application_key(self, *, job_id: int, requisition: str,
                        account_id: str | None = None, tenant: str | None = None) -> str:
        if self.production and (not account_id or not tenant):
            raise ValueError("production requires complete immutable application identity")
        return application_key(job_id=job_id, requisition=requisition, account_id=account_id, tenant=tenant)

    def attempt_for_application(self, *, job_id: int, requisition: str,
                                account_id: str | None = None, tenant: str | None = None) -> dict | None:
        key = self.application_key(job_id=job_id, requisition=requisition, account_id=account_id, tenant=tenant)
        with self.transaction() as connection:
            row = connection.execute("""SELECT * FROM submission_attempts WHERE application_key = ?
                ORDER BY (state != 'released') DESC, rowid DESC LIMIT 1""", (key,)).fetchone()
            return dict(row) if row else None

    def import_historical_attempt(
        self, *, source_id: str, evidence_sha256: str, trusted: bool,
        job_id: int, requisition: str, state: str, attempted_at: str | datetime,
        confirmed_at: str | datetime | None = None,
        account_id: str | None = None, tenant: str | None = None,
    ) -> dict:
        """Import verified history before exclusive enablement; never new dispatch.

        Pacing does not reject historical facts. No raw source/evidence/identity
        is persisted. The importer, not this library, verifies source truth.
        """
        if (trusted is not True or not isinstance(source_id, str) or not source_id
                or not isinstance(evidence_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", evidence_sha256)
                or state not in {"unknown", "confirmed"}
                or (state == "confirmed") != (confirmed_at is not None)):
            raise ValueError("trusted coherent historical submission evidence is required")
        key = self.application_key(job_id=job_id, requisition=requisition, account_id=account_id, tenant=tenant)
        attempted = parse_timestamp(attempted_at).isoformat()
        confirmed_time = parse_timestamp(confirmed_at).isoformat() if confirmed_at is not None else None
        if confirmed_time is not None and parse_timestamp(confirmed_time) < parse_timestamp(attempted):
            raise ValueError("historical confirmation cannot precede submission")
        source_digest = hashlib.sha256(source_id.encode()).hexdigest()
        payload_digest = hashlib.sha256(json.dumps(
            [key, state, attempted, confirmed_time, evidence_sha256], separators=(",", ":")
        ).encode()).hexdigest()
        with self.transaction() as connection:
            previous = connection.execute("SELECT * FROM submission_imports WHERE source_digest = ?", (source_digest,)).fetchone()
            if previous:
                if previous["payload_digest"] != payload_digest:
                    raise PermissionError("historical import source conflict")
                return dict(connection.execute("SELECT * FROM submission_attempts WHERE submission_attempt_id = ?",
                                               (previous["submission_attempt_id"],)).fetchone())
            assert_application_available(connection, key)
            attempt_id = secrets.token_hex(16)
            connection.execute("""INSERT INTO submission_attempts
                (submission_attempt_id, application_key, state, reserved_at, dispatched_at, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?)""", (attempt_id, key, state, attempted, attempted, confirmed_time))
            connection.execute("INSERT INTO submission_imports VALUES (?, ?, ?)",
                               (source_digest, payload_digest, attempt_id))
            return dict(connection.execute("SELECT * FROM submission_attempts WHERE submission_attempt_id = ?",
                                           (attempt_id,)).fetchone())

    def mark_dispatch(self, attempt_id: str, *, now: str | datetime) -> None:
        """Commit uncertainty BEFORE calling the browser, and permit this once."""
        with self.transaction() as connection:
            changed = connection.execute("""UPDATE submission_attempts
                SET state = 'unknown', dispatched_at = ?
                WHERE submission_attempt_id = ? AND state = 'reserved'""",
                (_transition_time(connection, attempt_id, now), attempt_id))
            if changed.rowcount != 1:
                raise PermissionError("submission dispatch is not replayable")

    def release_before_dispatch(self, attempt_id: str, *, now: str | datetime) -> None:
        """Only same-invocation known failure; NEVER call on crash recovery."""
        with self.transaction() as connection:
            changed = connection.execute("""UPDATE submission_attempts
                SET state = 'released', released_at = ?
                WHERE submission_attempt_id = ? AND state = 'reserved'""",
                (_transition_time(connection, attempt_id, now), attempt_id))
            if changed.rowcount != 1:
                raise PermissionError("cannot release a possibly dispatched submission")

    def confirm(self, attempt_id: str, *, now: str | datetime, confirmed: bool) -> None:
        """Positive exact ATS confirmation only; repeat observation is idempotent."""
        if confirmed is not True:
            raise PermissionError("positive confirmation is required")
        with self.transaction() as connection:
            row = connection.execute("SELECT state FROM submission_attempts WHERE submission_attempt_id = ?", (attempt_id,)).fetchone()
            if row and row[0] == "confirmed":
                return
            changed = connection.execute("""UPDATE submission_attempts
                SET state = 'confirmed', confirmed_at = ?
                WHERE submission_attempt_id = ? AND state = 'unknown'""",
                (_transition_time(connection, attempt_id, now), attempt_id))
            if changed.rowcount != 1:
                raise PermissionError("confirmation requires dispatched submission intent")
