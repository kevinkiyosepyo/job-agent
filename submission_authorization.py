"""Durable expiring, single-use authorization bound to exact Review evidence."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BINDING_KEYS = (
    "job_id",
    "target_id",
    "page_url",
    "requisition",
    "review_evidence_sha256",
)


def _parse_timestamp(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _isoformat(value: str | datetime) -> str:
    return _parse_timestamp(value).isoformat()


def _review_hash(review_evidence: dict) -> str:
    artifact = dict(review_evidence)
    supplied = artifact.pop("review_evidence_sha256", None)
    if not isinstance(supplied, str) or len(supplied) != 64:
        raise ValueError("authoritative Review hash is required")
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    calculated = hashlib.sha256(canonical).hexdigest()
    if not secrets.compare_digest(supplied, calculated):
        raise ValueError("authoritative Review hash does not match its evidence")
    return supplied


def _review_binding(review_evidence: dict, *, job_id: int) -> dict[str, object]:
    if (
        review_evidence.get("review_authoritative") is not True
        or review_evidence.get("submission_authorized") is not False
        or review_evidence.get("human_required") != []
    ):
        raise ValueError("authoritative Review evidence is required")
    evidence = review_evidence.get("evidence", {})
    binding = review_evidence.get("binding", {})
    if (
        not isinstance(evidence, dict)
        or evidence.get("sanitized") is not True
        or not isinstance(binding, dict)
        or binding.get("verified") is not True
    ):
        raise ValueError("authoritative Review evidence is required")
    review_hash = _review_hash(review_evidence)
    result: dict[str, object] = {
        "job_id": job_id,
        "target_id": binding.get("target_id"),
        "page_url": binding.get("page_url"),
        "requisition": binding.get("requisition"),
        "review_evidence_sha256": review_hash,
    }
    if not isinstance(job_id, int) or job_id <= 0 or not all(
        isinstance(result[key], str) and bool(result[key])
        for key in BINDING_KEYS
        if key != "job_id"
    ):
        raise ValueError("authoritative Review binding is incomplete")
    return result


class SubmissionAuthorizationStore:
    """Issue and atomically consume exact-bound submission authorizations."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS submission_authorizations (
                    token_digest TEXT PRIMARY KEY,
                    job_id INTEGER NOT NULL,
                    target_id TEXT NOT NULL,
                    page_url TEXT NOT NULL,
                    requisition TEXT NOT NULL,
                    review_evidence_sha256 TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    invalidated_at TEXT,
                    invalidation_reason TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def issue(
        self,
        *,
        job_id: int,
        review_evidence: dict,
        actor: str,
        issued_at: str | datetime,
        expires_at: str | datetime,
    ) -> dict[str, Any]:
        binding = _review_binding(review_evidence, job_id=job_id)
        if not isinstance(actor, str) or not actor:
            raise ValueError("authorization actor is required")
        issued = _parse_timestamp(issued_at)
        expires = _parse_timestamp(expires_at)
        if expires <= issued:
            raise ValueError("authorization expiry must be after issuance")

        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO submission_authorizations (
                    token_digest, job_id, target_id, page_url, requisition,
                    review_evidence_sha256, actor, issued_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    digest,
                    binding["job_id"],
                    binding["target_id"],
                    binding["page_url"],
                    binding["requisition"],
                    binding["review_evidence_sha256"],
                    actor,
                    issued.isoformat(),
                    expires.isoformat(),
                ),
            )
        return {
            "token": token,
            "single_use": True,
            "binding": {**binding, "actor": actor},
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
        }

    def consume(
        self,
        *,
        token: str,
        current_binding: dict,
        actor: str,
        now: str | datetime,
    ) -> dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise PermissionError("submission authorization is invalid")
        if not isinstance(current_binding, dict):
            raise PermissionError("submission authorization binding drift detected")
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        current_time = _parse_timestamp(now)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT job_id, target_id, page_url, requisition,
                       review_evidence_sha256, actor, expires_at, used_at,
                       invalidated_at
                FROM submission_authorizations
                WHERE token_digest = ?
                """,
                (digest,),
            ).fetchone()
            if row is None or row[5] != actor:
                connection.rollback()
                raise PermissionError("submission authorization is invalid")
            if row[7] is not None:
                connection.rollback()
                raise PermissionError("submission authorization was replayed")
            if row[8] is not None:
                connection.rollback()
                raise PermissionError("submission authorization was invalidated")
            if _parse_timestamp(row[6]) <= current_time:
                connection.rollback()
                raise PermissionError("submission authorization has expired")

            expected_binding = dict(zip(BINDING_KEYS, row[:5]))
            supplied_binding = {key: current_binding.get(key) for key in BINDING_KEYS}
            if supplied_binding != expected_binding:
                connection.execute(
                    """
                    UPDATE submission_authorizations
                    SET invalidated_at = ?, invalidation_reason = ?
                    WHERE token_digest = ? AND used_at IS NULL AND invalidated_at IS NULL
                    """,
                    (current_time.isoformat(), "binding_drift", digest),
                )
                connection.commit()
                raise PermissionError("submission authorization binding drift detected")

            updated = connection.execute(
                """
                UPDATE submission_authorizations
                SET used_at = ?
                WHERE token_digest = ? AND used_at IS NULL AND invalidated_at IS NULL
                """,
                (current_time.isoformat(), digest),
            )
            if updated.rowcount != 1:
                connection.rollback()
                raise PermissionError("submission authorization was replayed")
            connection.commit()
            return {
                "authorization_consumed": True,
                "single_use": True,
                "binding": {**expected_binding, "actor": actor},
                "expires_at": _isoformat(row[6]),
                "consumed_at": current_time.isoformat(),
            }
        finally:
            connection.close()
