"""Final non-submitting production-readiness audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUPPORTED_PLATFORMS = ("greenhouse", "lever", "oracle", "workday")
HUMAN_ONLY_GATES = [
    "CAPTCHA",
    "email_or_identity_verification",
    "assessments",
    "unknown_required_questions",
    "explicit_submission_authorization",
]


def build_audit(
    *, dry_run_verification: dict[str, Any], fixture_flows: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Return a safe readiness verdict from persisted non-submitting evidence."""
    dry_run_verified = all(
        dry_run_verification.get(key) is expected
        for key, expected in {
            "idempotent_queueing": True,
            "unsupported_roles_not_queued": True,
            "submission_enabled": False,
            "external_side_effects_blocked": True,
        }.items()
    )
    fixture_flows_verified = sorted(
        platform
        for platform in SUPPORTED_PLATFORMS
        if fixture_flows.get(platform, {}).get("submission_enabled") is False
        and fixture_flows[platform].get("plan", {}).get("platform") == platform
    )
    ready = dry_run_verified and fixture_flows_verified == list(SUPPORTED_PLATFORMS)
    return {
        "status": "ready_for_human_gated_production" if ready else "not_ready",
        "dry_run_verified": dry_run_verified,
        "fixture_flows_verified": fixture_flows_verified,
        "human_only_gates": list(HUMAN_ONLY_GATES),
    }


def main(argv: list[str] | None = None) -> int:
    """Audit persisted dry-run and fixture evidence without external mutation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run-report", required=True)
    parser.add_argument("--fixture-flows", required=True)
    args = parser.parse_args(argv)
    dry_run = json.loads(Path(args.dry_run_report).read_text(encoding="utf-8"))
    fixture_flows = json.loads(Path(args.fixture_flows).read_text(encoding="utf-8"))
    if not isinstance(dry_run, dict) or not isinstance(dry_run.get("verification"), dict):
        raise ValueError("dry-run report must contain a verification object")
    if not isinstance(fixture_flows, dict):
        raise ValueError("fixture flows must be a JSON object")
    report = build_audit(
        dry_run_verification=dry_run["verification"], fixture_flows=fixture_flows
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "ready_for_human_gated_production" else 1


if __name__ == "__main__":
    raise SystemExit(main())
