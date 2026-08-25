#!/usr/bin/env python3
"""Production-safe dry-run command that chains sources and orchestrator."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path

import orchestrator
import sources


BASE = Path.home() / "Documents/job-agent"


def _run_main(main_func, argv: list[str]) -> tuple[int, dict]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = main_func(argv)
    payload = json.loads(stdout.getvalue())
    return exit_code, payload


def _orchestrator_argv(
    *,
    candidates_path: Path,
    profile_path: Path,
    orchestrator_report_path: Path,
    queue_db_path: Path,
    audit_log_path: Path,
    source_report_path: Path,
) -> list[str]:
    return [
        str(candidates_path),
        "--profile",
        str(profile_path),
        "--output",
        str(orchestrator_report_path),
        "--queue-db",
        str(queue_db_path),
        "--audit-log",
        str(audit_log_path),
        "--source-report",
        str(source_report_path),
    ]


def _build_verification(first_payload: dict, second_payload: dict) -> dict:
    first_queue_count = first_payload.get("queue", {}).get("count")
    second_queue_count = second_payload.get("queue", {}).get("count")
    unsupported_count = second_payload.get("plan", {}).get("counts", {}).get("unsupported", 0)
    supported_queue_count = (
        second_payload.get("plan", {}).get("counts", {}).get("greenhouse", 0)
        + second_payload.get("plan", {}).get("counts", {}).get("workday", 0)
    )
    submission_enabled = bool(second_payload.get("plan", {}).get("submission_enabled"))
    return {
        "idempotent_queueing": first_queue_count == second_queue_count,
        "first_queue_count": first_queue_count,
        "second_queue_count": second_queue_count,
        "unsupported_roles_not_queued": second_queue_count == supported_queue_count and unsupported_count >= 0,
        "submission_enabled": submission_enabled,
        "external_side_effects_blocked": not submission_enabled,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--greenhouse", action="append", default=[], help="Greenhouse board token")
    parser.add_argument("--lever", action="append", default=[], help="Lever company token")
    parser.add_argument("--profile", default=str(BASE / "profile.json"))
    parser.add_argument("--workspace", default=str(BASE / "runtime/production-run"))
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    candidates_path = workspace / "candidates.json"
    source_report_path = workspace / "sources-report.json"
    orchestrator_report_path = workspace / "orchestrator-report.json"
    queue_db_path = workspace / "app_queue.sqlite3"
    audit_log_path = workspace / "audit.jsonl"

    source_argv: list[str] = ["--output", str(candidates_path), "--report", str(source_report_path)]
    for token in args.greenhouse:
        source_argv.extend(["--greenhouse", token])
    for token in args.lever:
        source_argv.extend(["--lever", token])

    source_exit_code, source_payload = _run_main(sources.main, source_argv)

    result = {
        "mode": "production_safe_dry_run",
        "workspace": str(workspace),
        "candidates_path": str(candidates_path),
        "source_report_path": str(source_report_path),
        "orchestrator_report_path": str(orchestrator_report_path),
        "source_exit_code": source_exit_code,
        "source": source_payload,
    }

    if source_exit_code != 0:
        print(json.dumps(result))
        return source_exit_code

    orchestrator_argv = _orchestrator_argv(
        candidates_path=candidates_path,
        profile_path=Path(args.profile),
        orchestrator_report_path=orchestrator_report_path,
        queue_db_path=queue_db_path,
        audit_log_path=audit_log_path,
        source_report_path=source_report_path,
    )
    orchestrator_exit_code, orchestrator_payload = _run_main(orchestrator.main, orchestrator_argv)
    result["orchestrator_exit_code"] = orchestrator_exit_code
    result["orchestrator"] = orchestrator_payload
    if orchestrator_exit_code == 0:
        _, second_orchestrator_payload = _run_main(orchestrator.main, orchestrator_argv)
        result["verification"] = _build_verification(orchestrator_payload, second_orchestrator_payload)
    print(json.dumps(result))
    return orchestrator_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
