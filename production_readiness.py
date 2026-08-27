"""Final non-submitting production-readiness audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUPPORTED_PLATFORMS = ("greenhouse", "lever", "oracle", "workday")
LEARNED_ATS_PLATFORM = "njoyn"
CANARY_PLATFORMS = ("greenhouse", "lever", "njoyn", "oracle", "workday")
PREPARATION_TARGET_SECONDS = 5 * 60
VERIFIED_SUBMISSION_TARGET_SECONDS = 10 * 60
LEARNED_ATS_SAFETY_INVARIANTS = (
    "submission_enabled",
    "external_side_effects_blocked",
    "parser_repair_required",
    "review_required",
    "confirmation_required",
    "tracker_readback_required",
    "discord_readback_required",
)
HUMAN_ONLY_GATES = [
    "CAPTCHA",
    "email_or_identity_verification",
    "assessments",
    "unknown_required_questions",
    "explicit_submission_authorization",
]


def build_audit(
    *,
    dry_run_verification: dict[str, Any],
    fixture_flows: dict[str, dict[str, Any]],
    learned_ats_benchmark: dict[str, Any] | None = None,
    browser_canaries: dict[str, dict[str, Any]] | None = None,
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
    browser_canaries_verified = (
        sorted(
            platform
            for platform in CANARY_PLATFORMS
            if browser_canaries.get(platform, {}).get("status") == "passed"
            and browser_canaries[platform].get("submission_enabled") is False
        )
        if browser_canaries is not None
        else None
    )
    benchmark_report = None
    if learned_ats_benchmark is not None:
        safety_invariants_verified = (
            learned_ats_benchmark.get("submission_enabled") is False
            and all(
                learned_ats_benchmark.get(key) is True
                for key in LEARNED_ATS_SAFETY_INVARIANTS
                if key != "submission_enabled"
            )
        )
        preparation_within_target = (
            learned_ats_benchmark.get("platform") == LEARNED_ATS_PLATFORM
            and isinstance(learned_ats_benchmark.get("preparation_seconds"), (int, float))
            and not isinstance(learned_ats_benchmark["preparation_seconds"], bool)
            and learned_ats_benchmark["preparation_seconds"] < PREPARATION_TARGET_SECONDS
        )
        verified_submission_within_target = (
            isinstance(learned_ats_benchmark.get("verified_submission_seconds"), (int, float))
            and not isinstance(learned_ats_benchmark["verified_submission_seconds"], bool)
            and learned_ats_benchmark["verified_submission_seconds"] < VERIFIED_SUBMISSION_TARGET_SECONDS
        )
        benchmark_report = {
            "platform": learned_ats_benchmark.get("platform"),
            "preparation_within_target": preparation_within_target,
            "verified_submission_within_target": verified_submission_within_target,
            "safety_invariants_verified": safety_invariants_verified,
            "ready": (
                preparation_within_target
                and verified_submission_within_target
                and safety_invariants_verified
            ),
        }
    ready = (
        dry_run_verified
        and fixture_flows_verified == list(SUPPORTED_PLATFORMS)
        and (browser_canaries_verified is None or browser_canaries_verified == list(CANARY_PLATFORMS))
        and (benchmark_report is None or benchmark_report["ready"])
    )
    report = {
        "status": "ready_for_human_gated_production" if ready else "not_ready",
        "dry_run_verified": dry_run_verified,
        "fixture_flows_verified": fixture_flows_verified,
        "human_only_gates": list(HUMAN_ONLY_GATES),
    }
    if browser_canaries_verified is not None:
        report["browser_canaries_verified"] = browser_canaries_verified
    if benchmark_report is not None:
        report["learned_ats_benchmark"] = benchmark_report
    return report


def main(argv: list[str] | None = None) -> int:
    """Audit persisted dry-run and fixture evidence without external mutation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run-report", required=True)
    parser.add_argument("--fixture-flows", required=True)
    parser.add_argument("--learned-ats-benchmark")
    parser.add_argument("--browser-canaries")
    args = parser.parse_args(argv)
    dry_run = json.loads(Path(args.dry_run_report).read_text(encoding="utf-8"))
    fixture_flows = json.loads(Path(args.fixture_flows).read_text(encoding="utf-8"))
    learned_ats_benchmark = (
        json.loads(Path(args.learned_ats_benchmark).read_text(encoding="utf-8"))
        if args.learned_ats_benchmark
        else None
    )
    browser_canaries = (
        json.loads(Path(args.browser_canaries).read_text(encoding="utf-8"))
        if args.browser_canaries
        else None
    )
    if not isinstance(dry_run, dict) or not isinstance(dry_run.get("verification"), dict):
        raise ValueError("dry-run report must contain a verification object")
    if not isinstance(fixture_flows, dict):
        raise ValueError("fixture flows must be a JSON object")
    if learned_ats_benchmark is not None and not isinstance(learned_ats_benchmark, dict):
        raise ValueError("learned ATS benchmark must be a JSON object")
    if browser_canaries is not None and not isinstance(browser_canaries, dict):
        raise ValueError("browser canaries must be a JSON object")
    report = build_audit(
        dry_run_verification=dry_run["verification"],
        fixture_flows=fixture_flows,
        learned_ats_benchmark=learned_ats_benchmark,
        browser_canaries=browser_canaries,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "ready_for_human_gated_production" else 1


if __name__ == "__main__":
    raise SystemExit(main())
