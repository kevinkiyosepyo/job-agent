#!/usr/bin/env python3
"""Offline setup diagnostics for the Hermes job agent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import browser_health

BASE = Path.home() / "Documents/job-agent"
DEFAULT_OAUTH_TOKEN = Path.home() / ".hermes/google_token.json"

BrowserProbe = Callable[[str], dict]


def _profile_check(profile_path: Path) -> dict:
    if not profile_path.exists():
        return {
            "status": "blocking",
            "error_code": "missing_profile",
            "message": f"Profile not found: {profile_path}",
        }

    profile = json.loads(profile_path.read_text())
    resume_path = Path(profile.get("resume", {}).get("primary", "")).expanduser()
    if not str(resume_path):
        return {
            "status": "blocking",
            "error_code": "missing_resume_path",
            "message": "Profile is missing resume.primary",
        }
    if not resume_path.exists():
        return {
            "status": "blocking",
            "error_code": "missing_resume_file",
            "message": f"Resume file not found: {resume_path}",
        }

    email = (profile.get("contact", {}).get("email") or "").strip()
    if not email:
        return {
            "status": "blocking",
            "error_code": "missing_contact_email",
            "message": "Profile is missing contact.email",
        }

    return {
        "status": "ready",
        "error_code": None,
        "message": "Profile, contact email, and resume file are present",
        "resume_path": str(resume_path),
    }


def _oauth_check(oauth_token_path: Path) -> dict:
    if oauth_token_path.exists():
        return {
            "status": "ready",
            "error_code": None,
            "message": f"OAuth token present: {oauth_token_path}",
        }
    return {
        "status": "blocking",
        "error_code": "missing_google_oauth_token",
        "message": f"Google Sheets write token not found: {oauth_token_path}",
    }


def run_checks(
    profile_path: Path,
    *,
    browser_base_url: str = "http://127.0.0.1:9222",
    probe_browser: BrowserProbe = browser_health.probe_cdp_health,
    oauth_token_path: Path = DEFAULT_OAUTH_TOKEN,
    skip_browser: bool = False,
) -> dict:
    profile = _profile_check(Path(profile_path))
    oauth = _oauth_check(Path(oauth_token_path))

    if skip_browser:
        browser = {
            "status": "skipped",
            "error_code": "skipped_by_flag",
            "message": "Skipped browser check by request",
        }
    elif profile["status"] != "ready":
        browser = {
            "status": "skipped",
            "error_code": "profile_blocking_issue",
            "message": "Skipped browser check because profile prerequisites failed",
        }
    else:
        browser = probe_browser(browser_base_url)

    checks = {
        "profile": profile,
        "oauth": oauth,
        "browser": browser,
    }
    ready = all(check["status"] in {"ready", "skipped"} for check in checks.values())
    return {
        "status": "ready" if ready else "blocking",
        "ready": ready,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=str(BASE / "profile.json"))
    parser.add_argument("--browser-base-url", default="http://127.0.0.1:9222")
    parser.add_argument("--oauth-token", default=str(DEFAULT_OAUTH_TOKEN))
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args(argv)

    payload = run_checks(
        Path(args.profile),
        browser_base_url=args.browser_base_url,
        oauth_token_path=Path(args.oauth_token),
        skip_browser=args.skip_browser,
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
