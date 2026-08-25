#!/usr/bin/env python3
"""Deterministic Discord control helpers for queue-bound job actions."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import app_queue


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


def _parse_control_id(control_id: str) -> tuple[str, int]:
    try:
        prefix, raw_job_id, action = control_id.split(":", 2)
    except ValueError as exc:
        raise ValueError("Invalid control id") from exc
    if prefix != "job" or not raw_job_id.isdigit() or action not in _ACTIONS:
        raise ValueError("Invalid control id")
    return action, int(raw_job_id)


def handle_control(queue: app_queue.ApplicationQueue, *, control_id: str) -> dict:
    action, job_id = _parse_control_id(control_id)
    job = next((candidate for candidate in queue.list_jobs() if candidate.id == job_id), None)
    if job is None:
        raise KeyError(job_id)
    spec = _ACTIONS[action]
    if job.state not in spec["allowed_states"]:
        raise ValueError(f"Control {action} is not valid for state {job.state}")
    updated = queue.transition(job_id, spec["target_state"])
    return {
        "control_id": control_id,
        "action": action,
        "status": spec["status"],
        "job": asdict(updated),
    }


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
