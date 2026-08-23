#!/usr/bin/env python3
"""Persistent SQLite application queue with idempotent job insertion."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
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


VALID_STATES = ("discovered", "prepared", "applied")
ALLOWED_TRANSITIONS = {
    "discovered": {"prepared"},
    "prepared": {"applied"},
    "applied": set(),
}


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
                    state TEXT NOT NULL
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
                "UPDATE application_queue SET state = ? WHERE id = ?",
                (target, job_id),
            )
            updated = self._fetch_row(conn, job_id=job_id)
        assert updated is not None
        return QueueJob(*updated)

    def _fetch_row(self, conn: sqlite3.Connection, *, normalized_url: str | None = None, job_id: int | None = None):
        if normalized_url is not None:
            return conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state
                FROM application_queue
                WHERE normalized_url = ?
                """,
                (normalized_url,),
            ).fetchone()
        return conn.execute(
            """
            SELECT id, company, role, normalized_url, ats_platform, state
            FROM application_queue
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    def list_jobs(self) -> list[QueueJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, company, role, normalized_url, ats_platform, state
                FROM application_queue
                ORDER BY id
                """
            ).fetchall()
        return [QueueJob(*row) for row in rows]
