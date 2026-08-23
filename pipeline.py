#!/usr/bin/env python3
"""Safety-focused router and submission recorder for the job agent."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

BASE = Path.home() / "Documents/job-agent"


def route_candidates(scan: dict) -> dict[str, list[dict]]:
    routed: dict[str, list[dict]] = {
        "greenhouse": [],
        "workday": [],
        "unsupported": [],
        "manual_only": list(scan.get("manual_only", [])),
    }
    for job in scan.get("auto_apply_queue", []):
        ats = (job.get("ats_platform") or "").casefold()
        if ats == "greenhouse":
            routed["greenhouse"].append(job)
        elif ats == "workday":
            routed["workday"].append(job)
        else:
            routed["unsupported"].append(job)
    return routed


def submission_row(job: dict, *, confirmation_url: str, confirmation_text: str) -> list[str]:
    evidence = " ".join((confirmation_url.strip(), confirmation_text.strip())).strip()
    if not evidence:
        raise ValueError("Verified confirmation evidence is required before recording submission")
    notes = f"Confirmation verified: {confirmation_text.strip() or confirmation_url.strip()}"
    if confirmation_url.strip() and confirmation_text.strip():
        notes += f" ({confirmation_url.strip()})"
    return [
        job["company"].strip(),
        "Submitted - Pending Response",
        job["role"].strip(),
        (job.get("salary") or "").strip(),
        date.today().isoformat(),
        job["url"].strip(),
        "N/A",
        notes,
    ]


def validate_profile(profile: dict) -> list[str]:
    errors: list[str] = []
    for path in (("name", "full"), ("contact", "email"), ("contact", "phone"), ("resume", "primary")):
        value = profile
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if not value:
            errors.append(".".join(path))
    resume = Path(profile.get("resume", {}).get("primary", "")).expanduser()
    if str(resume) and not resume.is_file():
        errors.append("resume.primary:file_missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scan", help="scanner.py JSON output")
    parser.add_argument("--profile", default=str(BASE / "profile.json"))
    parser.add_argument("--output", default=str(BASE / "pipeline-plan.json"))
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).read_text())
    errors = validate_profile(profile)
    if errors:
        raise SystemExit("Invalid profile: " + ", ".join(errors))
    scan = json.loads(Path(args.scan).read_text())
    routed = route_candidates(scan)
    payload = {
        "mode": "plan_only",
        "submission_enabled": False,
        "routes": routed,
        "counts": {key: len(value) for key, value in routed.items()},
    }
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
