#!/usr/bin/env python3
"""Deterministic Discord control helpers for queue-bound job actions."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from dataclasses import asdict
from typing import Iterable

import app_queue
from audit_log import AuditLogger


_ACTIONS = {
    "approve": {
        "allowed_states": {"pending_approval"},
        "target_state": "discovered",
        "status": "approved",
    },
    "reject": {
        "allowed_states": {"pending_approval"},
        "target_state": "failed",
        "status": "rejected",
    },
    "retry": {
        "allowed_states": {"pending_question", "pending_captcha"},
        "target_state": "discovered",
        "status": "retried",
    },
    "skip": {
        "allowed_states": {"pending_question", "pending_captcha"},
        "target_state": "failed",
        "status": "skipped",
    },
}


def controls_for_job(job: app_queue.QueueJob) -> list[dict[str, str]]:
    actions = [
        action
        for action, spec in _ACTIONS.items()
        if job.state in spec["allowed_states"]
    ]
    return [{"action": action, "control_id": build_control_id(action, job.id)} for action in actions]


def build_control_id(action: str, job_id: int) -> str:
    normalized = action.strip().casefold()
    if normalized not in _ACTIONS:
        raise ValueError(f"Unknown control action: {action}")
    return f"job:{job_id}:{normalized}"


def issue_control_token(
    queue: app_queue.ApplicationQueue,
    *,
    control_id: str,
    actor_id: str,
    expires_at: str | datetime,
) -> str:
    """Create a durable, actor- and control-bound Discord command token."""
    _parse_control_id(control_id)
    return queue.issue_discord_control_token(
        control_id=control_id,
        actor_id=actor_id,
        expires_at=expires_at,
    )


def _parse_control_id(control_id: str) -> tuple[str, int]:
    try:
        prefix, raw_job_id, action = control_id.split(":", 2)
    except ValueError as exc:
        raise ValueError("Invalid control id") from exc
    if prefix != "job" or not raw_job_id.isdigit() or action not in _ACTIONS:
        raise ValueError("Invalid control id")
    return action, int(raw_job_id)


def _default_now() -> datetime:
    return datetime.now(UTC)


def _audit_denial(audit_logger: AuditLogger | None, *, actor_id: str | None, control_id: str, reason: str) -> None:
    if audit_logger is not None:
        audit_logger.log(
            "discord_queue_control_denied",
            {"actor_id": actor_id, "control_id": control_id, "reason": reason},
        )


def handle_control(
    queue: app_queue.ApplicationQueue,
    *,
    control_id: str,
    actor_id: str | None = None,
    allowed_actor_ids: Iterable[str] | None = None,
    audit_logger: AuditLogger | None = None,
    token: str | None = None,
    now: str | datetime | None = None,
) -> dict:
    """Apply a job-bound control, optionally enforcing the Discord actor allowlist."""
    if allowed_actor_ids is not None and actor_id not in {str(value) for value in allowed_actor_ids}:
        _audit_denial(audit_logger, actor_id=actor_id, control_id=control_id, reason="unauthorized_actor")
        raise PermissionError("Discord actor is not authorized for queue controls")
    if token is not None:
        try:
            queue.consume_discord_control_token(
                token=token,
                control_id=control_id,
                actor_id=str(actor_id),
                now=now or _default_now(),
            )
        except PermissionError as exc:
            reason = "token_replayed" if "replayed" in str(exc) else "invalid_or_expired_token"
            _audit_denial(audit_logger, actor_id=actor_id, control_id=control_id, reason=reason)
            raise
    action, job_id = _parse_control_id(control_id)
    job = next((candidate for candidate in queue.list_jobs() if candidate.id == job_id), None)
    if job is None:
        raise KeyError(job_id)
    spec = _ACTIONS[action]
    if job.state not in spec["allowed_states"]:
        raise ValueError(f"Control {action} is not valid for state {job.state}")
    updated = queue.transition(job_id, spec["target_state"])
    result = {
        "control_id": control_id,
        "action": action,
        "status": spec["status"],
        "job": asdict(updated),
    }
    if audit_logger is not None:
        audit_logger.log(
            "discord_queue_control_applied",
            {
                "action": action,
                "actor_id": actor_id,
                "control_id": control_id,
                "job_id": job_id,
                "status": spec["status"],
            },
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("control_id")
    parser.add_argument("--queue-db", required=True)
    args = parser.parse_args(argv)

    queue = app_queue.ApplicationQueue(args.queue_db)
    payload = handle_control(queue, control_id=args.control_id)
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
