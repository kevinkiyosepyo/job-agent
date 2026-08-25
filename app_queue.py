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


VALID_STATES = (
    "discovered",
    "leased",
    "prepared",
    "pending_question",
    "pending_captcha",
    "pending_approval",
    "failed",
    "applied",
)
ALLOWED_TRANSITIONS = {
    "discovered": {"prepared"},
    "leased": {"discovered", "prepared", "pending_question", "pending_captcha", "pending_approval", "failed", "applied"},
    "prepared": {"applied"},
    "pending_question": {"discovered", "prepared", "failed"},
    "pending_captcha": {"discovered", "prepared", "failed"},
    "pending_approval": {"discovered", "prepared", "failed"},
    "failed": set(),
    "applied": set(),
}
LEASE_OUTCOMES = {
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
    return dt.isoformat()


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    keep = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"ref", "source", "trk", "trackingid"}
    ]
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"), urlencode(keep), ""))


class ApplicationQueue:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
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
            ):
                if name not in columns:
                    conn.execute(ddl)
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
                (company.strip(), role.strip(), normalized_url, ats_platform.strip(), VALID_STATES[0]),
            )
            row = self._fetch_row(conn, normalized_url=normalized_url)
        assert row is not None
        return QueueJob(*row)

    def transition(self, job_id: int, state: str) -> QueueJob:
        target = state.strip().casefold()
        if target not in VALID_STATES:
            raise ValueError(f"Unknown state: {state}")
        with self._connect() as conn:
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise KeyError(job_id)
            job = QueueJob(*row)
            if job.state == target:
                return job
            if target not in ALLOWED_TRANSITIONS[job.state]:
                raise ValueError(f"Invalid transition: {job.state} -> {target}")
            conn.execute(
                "UPDATE application_queue SET state = ?, available_at = NULL, lease_expires_at = NULL WHERE id = ?",
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
            row = conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state,
                       attempt_count, available_at, lease_expires_at, last_error
                FROM application_queue
                WHERE (
                        state = 'discovered'
                        OR (state = 'leased' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?)
                      )
                  AND (available_at IS NULL OR available_at <= ?)
                """ + exclusions + """
                ORDER BY id
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
                    last_error = NULL
                WHERE id = ?
                """,
                (lease_expires_at, job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def finish_lease(
        self,
        job_id: int,
        *,
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
        if target == "discovered":
            available_at = _isoformat(completed_at + timedelta(seconds=max(0, retry_seconds)))
        with self._connect() as conn:
            row = self._fetch_row(conn, job_id=job_id)
            if row is None:
                raise KeyError(job_id)
            job = QueueJob(*row)
            if job.state != "leased":
                raise ValueError(f"Job {job_id} is not currently leased")
            conn.execute(
                """
                UPDATE application_queue
                SET state = ?,
                    available_at = ?,
                    lease_expires_at = NULL,
                    last_error = ?
                WHERE id = ?
                """,
                (target, available_at, error, job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def _fetch_row(self, conn: sqlite3.Connection, *, normalized_url: str | None = None, job_id: int | None = None):
        if normalized_url is not None:
            return conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state
                       , attempt_count, available_at, lease_expires_at, last_error
                FROM application_queue
                WHERE normalized_url = ?
                """,
                (normalized_url,),
            ).fetchone()
        return conn.execute(
            """
            SELECT id, company, role, normalized_url, ats_platform, state,
                   attempt_count, available_at, lease_expires_at, last_error
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
                       attempt_count, available_at, lease_expires_at, last_error
                FROM application_queue
                ORDER BY id
                """
            ).fetchall()
        return [QueueJob(*row) for row in rows]

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
