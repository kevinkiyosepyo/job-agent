#!/usr/bin/env python3
"""Send structured job-agent notifications through Kevin's Discord bot."""
from __future__ import annotations

import argparse
import json
import os
import subprocess

DEFAULT_TARGET = "discord:937013921028644927"
ICON = {"maango": "⭐", "captcha": "🔒", "applied": "✅", "failed": "❌", "question": "❓", "scan": "🔎"}


def default_target() -> str:
    return os.environ.get("JOB_AGENT_DISCORD_TARGET", DEFAULT_TARGET)


def build_message(kind: str, *, company: str = "", role: str = "", url: str = "", detail: str = "") -> str:
    label = {
        "maango": "Manual application requested",
        "captcha": "Manual CAPTCHA needed",
        "applied": "Application submitted",
        "failed": "Application failed",
        "question": "Answer needed",
        "scan": "Job scan update",
    }[kind]
    lines = [f"{ICON[kind]} **{label}**"]
    if company:
        lines.append(f"Company: {company}")
    if role:
        lines.append(f"Role: {role}")
    if detail:
        lines.append(detail)
    if url:
        lines.append(url)
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=sorted(ICON))
    p.add_argument("--company", default="")
    p.add_argument("--role", default="")
    p.add_argument("--url", default="")
    p.add_argument("--detail", default="")
    p.add_argument("--target", default=default_target())
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    message = build_message(a.kind, company=a.company, role=a.role, url=a.url, detail=a.detail)
    if a.dry_run:
        print(json.dumps({"target": a.target, "message": message}, indent=2))
        return 0
    proc = subprocess.run(
        ["hermes", "send", "--to", a.target, "--json", message],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip())
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
