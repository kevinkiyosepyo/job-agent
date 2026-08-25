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

    orchestrator_exit_code, orchestrator_payload = _run_main(
        orchestrator.main,
        [
            str(candidates_path),
            "--profile",
            str(Path(args.profile)),
            "--output",
            str(orchestrator_report_path),
            "--queue-db",
            str(queue_db_path),
            "--audit-log",
            str(audit_log_path),
            "--source-report",
            str(source_report_path),
        ],
    )
    result["orchestrator_exit_code"] = orchestrator_exit_code
    result["orchestrator"] = orchestrator_payload
    print(json.dumps(result))
    return orchestrator_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
