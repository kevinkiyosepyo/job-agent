#!/usr/bin/env python3
"""Persistent SQLite application queue with idempotent job insertion."""
from __future__ import annotations

import sqlite3
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class QueueJob:
    id: int
    company: str
    role: str
    url: str
    ats_platform: str
    state: str
    attempt_count: int = 0
    available_at: str | None = None
    lease_expires_at: str | None = None
    last_error: str | None = None
    lease_token: str | None = None
    checkpoint_after_attempt: int = 0


PARKED_STATES = ("blocked_security", "blocked_fact", "blocked_approval",
                 "pending_captcha", "pending_question", "pending_approval", "submission_uncertain")

VALID_STATES = (
    "discovered",
    "leased",
    "prepared",
    "pending_question",
    "pending_captcha",
    "pending_approval",
    "failed",
    "applied",
    "blocked_security", "blocked_fact", "blocked_approval", "submission_uncertain",
)
ALLOWED_TRANSITIONS = {
    "discovered": {"prepared"},
    "blocked_security": {"discovered", "failed"},
    "blocked_fact": {"discovered", "failed"},
    "blocked_approval": {"discovered", "failed"},
    "submission_uncertain": {"applied"},
    "leased": {"discovered", "prepared", "pending_question", "pending_captcha", "pending_approval", "failed", "applied"},
    "prepared": {"applied"},
    "pending_question": {"discovered", "failed"},
    "pending_captcha": {"discovered", "failed"},
    "pending_approval": {"discovered", "failed"},
    "failed": set(),
    "applied": set(),
}
LEASE_OUTCOMES = {
    **{state: state for state in PARKED_STATES},
    "retry": "discovered",
    "prepared": "prepared",
    "pending_question": "pending_question",
    "pending_captcha": "pending_captcha",
    "pending_approval": "pending_approval",
    "failed": "failed",
    "applied": "applied",
}


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    keep = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"ref", "source", "trk", "trackingid"}
    ]
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), urlencode(keep), ""))


class LeaseLostError(ValueError):
    """Ownership was lost or expired; never retry using a replacement token."""


class ApplicationQueue:
    def __init__(self, path: Path, *, retry_budget: int = 3):
        self.retry_budget = max(1, retry_budget)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS application_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    role TEXT NOT NULL,
                    normalized_url TEXT NOT NULL UNIQUE,
                    ats_platform TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    available_at TEXT,
                    lease_expires_at TEXT,
                    last_error TEXT
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(application_queue)").fetchall()}
            for name, ddl in (
                ("attempt_count", "ALTER TABLE application_queue ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"),
                ("available_at", "ALTER TABLE application_queue ADD COLUMN available_at TEXT"),
                ("lease_expires_at", "ALTER TABLE application_queue ADD COLUMN lease_expires_at TEXT"),
                ("last_error", "ALTER TABLE application_queue ADD COLUMN last_error TEXT"),
                ("lease_token", "ALTER TABLE application_queue ADD COLUMN lease_token TEXT"),
                ("checkpoint_after_attempt", "ALTER TABLE application_queue ADD COLUMN checkpoint_after_attempt INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    conn.execute(ddl)
            conn.execute("""UPDATE application_queue SET state = 'submission_uncertain',
                         lease_expires_at = NULL, last_error = 'Legacy unfenced lease: inspect before recovery'
                         WHERE state = 'leased' AND lease_token IS NULL""")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS discord_control_tokens (
                    token TEXT PRIMARY KEY,
                    control_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                )
                """
            )

    def enqueue(self, *, company: str, role: str, url: str, ats_platform: str) -> QueueJob:
        normalized_url = normalize_url(url)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO application_queue (
                    company, role, normalized_url, ats_platform, state
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (company.strip(), role.strip(), normalized_url, ats_platform.strip(), "discovered"),
            )
            row = self._fetch_row(conn, normalized_url=normalized_url)
        assert row is not None
        return QueueJob(*row)

    def transition(self, job_id: int, state: str) -> QueueJob:
        target = state.strip().casefold()
        if target not in VALID_STATES:
            raise ValueError(f"Unknown state: {state}")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise KeyError(job_id)
            job = QueueJob(*row)
            if job.state == "leased":
                raise ValueError("Use finish_lease with the current lease token")
            if job.state == target:
                return job
            if target not in ALLOWED_TRANSITIONS[job.state]:
                raise ValueError(f"Invalid transition: {job.state} -> {target}")
            conn.execute(
                """UPDATE application_queue SET state = ?, available_at = NULL, lease_expires_at = NULL,
                   lease_token = NULL, checkpoint_after_attempt = attempt_count WHERE id = ?""",
                (target, job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def lease_next(
        self,
        *,
        now: str | datetime,
        lease_seconds: int,
        excluded_platforms: tuple[str, ...] = (),
    ) -> QueueJob | None:
        lease_started_at = _parse_timestamp(now)
        lease_expires_at = _isoformat(lease_started_at + timedelta(seconds=max(1, lease_seconds)))
        now_iso = _isoformat(lease_started_at)
        excluded = tuple(platform.casefold() for platform in excluded_platforms)
        exclusions = ""
        if excluded:
            exclusions = " AND lower(ats_platform) NOT IN (" + ", ".join("?" for _ in excluded) + ")"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state,
                       attempt_count, available_at, lease_expires_at, last_error, lease_token, checkpoint_after_attempt
                FROM application_queue
                WHERE (
                        state = 'discovered'
                        OR (state = 'leased' AND lease_expires_at IS NOT NULL AND julianday(lease_expires_at) <= julianday(?))
                      )
                  AND (available_at IS NULL OR julianday(available_at) <= julianday(?))
                """ + exclusions + """
                ORDER BY attempt_count, id
                LIMIT 1
                """,
                (now_iso, now_iso, *excluded),
            ).fetchone()
            if row is None:
                return None
            job_id = row[0]
            conn.execute(
                """
                UPDATE application_queue
                SET state = 'leased',
                    attempt_count = attempt_count + 1,
                    lease_expires_at = ?,
                    lease_token = ?,
                    last_error = NULL
                WHERE id = ?
                """,
                (lease_expires_at, secrets.token_urlsafe(32), job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def validate_lease(self, job_id: int, *, lease_token: str, now: str | datetime) -> QueueJob:
        """Read-only ownership check, not a lock covering subsequent external work."""
        with self._connect() as conn:
            row = self._fetch_row(conn, job_id=job_id)
        if row is None:
            raise KeyError(job_id)
        job = QueueJob(*row)
        if (job.state != "leased" or not lease_token or job.lease_token != lease_token
                or job.lease_expires_at is None
                or _parse_timestamp(job.lease_expires_at) <= _parse_timestamp(now)):
            raise LeaseLostError(f"Invalid or expired lease for job {job_id}")
        return job

    def heartbeat(
        self, job_id: int, *, lease_token: str, now: str | datetime, lease_seconds: int,
    ) -> QueueJob:
        """Renew a current capability; an expired lease cannot be resurrected."""
        current = _parse_timestamp(now)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise KeyError(job_id)
            job = QueueJob(*row)
            if (job.state != "leased" or not lease_token or job.lease_token != lease_token
                    or job.lease_expires_at is None
                    or _parse_timestamp(job.lease_expires_at) <= current):
                raise LeaseLostError(f"Invalid or expired lease for job {job_id}")
            expires = max(_parse_timestamp(job.lease_expires_at),
                          current + timedelta(seconds=max(1, lease_seconds)))
            conn.execute("UPDATE application_queue SET lease_expires_at = ? WHERE id = ?",
                         (_isoformat(expires), job_id))
            updated = self._fetch_row(conn, job_id=job_id)
        return QueueJob(*updated)

    def finish_lease(
        self,
        job_id: int,
        *,
        lease_token: str,
        outcome: str,
        now: str | datetime,
        retry_seconds: int = 0,
        error: str | None = None,
    ) -> QueueJob:
        target = LEASE_OUTCOMES.get(outcome.strip().casefold())
        if target is None:
            raise ValueError(f"Unknown lease outcome: {outcome}")
        completed_at = _parse_timestamp(now)
        available_at = None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise KeyError(job_id)
            job = QueueJob(*row)
            if (job.state != "leased" or not lease_token or job.lease_token != lease_token
                    or job.lease_expires_at is None
                    or _parse_timestamp(job.lease_expires_at) <= completed_at):
                raise LeaseLostError(f"Invalid or expired lease for job {job_id}")
            if target == "discovered" and job.attempt_count >= self.retry_budget:
                target = "failed"
                error = error or "Per-job retry budget exhausted"
            if target == "discovered":
                backoff = min(3600, 30 * 2 ** min(max(0, job.attempt_count - 1), 7))
                delay = min(3600, max(backoff, retry_seconds))
                available_at = _isoformat(completed_at + timedelta(seconds=delay))
            conn.execute(
                """
                UPDATE application_queue
                SET state = ?,
                    available_at = ?,
                    lease_expires_at = NULL,
                    lease_token = NULL,
                    last_error = ?
                WHERE id = ?
                """,
                (target, available_at, error, job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def recover_checkpoint(self, job_id: int, *, lease_token: str, checkpoint_phase: str,
                           outcome: str, now: str | datetime, error: str | None = None) -> QueueJob:
        """Consume an exact expired lease into a checkpoint-supported terminal state.

        Never renew or return a usable capability. A replacement owner (even an
        expired replacement) and any changed state are untouchable. Confirmed
        checkpoints are written only after independent positive ATS observation;
        uncertain intent can never become retryable through this operation.
        """
        allowed = ({'applied'} if checkpoint_phase == 'confirmed' else
                   {'submission_uncertain'} if checkpoint_phase in {'submitting','submission_uncertain'} else
                   {'blocked_fact','blocked_security','blocked_approval','failed'}
                   if checkpoint_phase in {'preparing','opening_target','reviewing','authorizing'} else set())
        if outcome not in allowed:
            raise ValueError('checkpoint does not support recovery outcome')
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise LeaseLostError(f'Checkpoint job {job_id} is unavailable')
            job = QueueJob(*row)
            if (job.state != 'leased' or not lease_token or job.lease_token != lease_token
                or job.lease_expires_at is None
                or _parse_timestamp(job.lease_expires_at) > _parse_timestamp(now)):
                raise LeaseLostError(f'Checkpoint ownership changed or still live for job {job_id}')
            conn.execute("""UPDATE application_queue SET state = ?, available_at = NULL,
                            lease_expires_at = NULL, lease_token = NULL, last_error = ?
                            WHERE id = ? AND state = 'leased' AND lease_token = ?""",
                         (outcome, error, job_id, lease_token))
            updated = self._fetch_row(conn, job_id=job_id)
        return QueueJob(*updated)

    def _fetch_row(self, conn: sqlite3.Connection, *, normalized_url: str | None = None, job_id: int | None = None):
        if normalized_url is not None:
            return conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state
                       , attempt_count, available_at, lease_expires_at, last_error, lease_token, checkpoint_after_attempt
                FROM application_queue
                WHERE normalized_url = ?
                """,
                (normalized_url,),
            ).fetchone()
        return conn.execute(
            """
            SELECT id, company, role, normalized_url, ats_platform, state,
                   attempt_count, available_at, lease_expires_at, last_error, lease_token, checkpoint_after_attempt
            FROM application_queue
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    def list_jobs(self) -> list[QueueJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state,
                       attempt_count, available_at, lease_expires_at, last_error, lease_token, checkpoint_after_attempt
                FROM application_queue
                ORDER BY id
                """
            ).fetchall()
        return [QueueJob(*row) for row in rows]

    def inspect_candidates(self, *, states: tuple[str, ...] | None = None) -> list[QueueJob]:
        """Read-only parked/uncertain inspection; never release a human gate."""
        selected = PARKED_STATES if states is None else states
        if any(state not in VALID_STATES for state in selected):
            raise ValueError("Unknown inspection state")
        return [job for job in self.list_jobs() if job.state in selected]

    def issue_discord_control_token(
        self,
        *,
        control_id: str,
        actor_id: str,
        expires_at: str | datetime,
    ) -> str:
        token = secrets.token_urlsafe(24)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO discord_control_tokens (token, control_id, actor_id, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, control_id, str(actor_id), _isoformat(_parse_timestamp(expires_at))),
            )
        return token

    def consume_discord_control_token(
        self,
        *,
        token: str,
        control_id: str,
        actor_id: str,
        now: str | datetime,
    ) -> None:
        now_iso = _isoformat(_parse_timestamp(now))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT control_id, actor_id, expires_at, used_at
                FROM discord_control_tokens WHERE token = ?
                """,
                (token,),
            ).fetchone()
            if row is None or row[0] != control_id or row[1] != str(actor_id):
                raise PermissionError("Discord control token is invalid")
            if row[3] is not None:
                raise PermissionError("Discord control token was replayed")
            if _parse_timestamp(row[2]) <= _parse_timestamp(now_iso):
                raise PermissionError("Discord control token has expired")
            updated = conn.execute(
                """
                UPDATE discord_control_tokens SET used_at = ?
                WHERE token = ? AND used_at IS NULL
                """,
                (now_iso, token),
            )
            if updated.rowcount != 1:
                raise PermissionError("Discord control token was replayed")
