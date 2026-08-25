#!/usr/bin/env python3
"""Non-submitting ATS prepare command over saved HTML."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ats_registry import resolve_handler
from resume_preflight import preflight_profile_resume


def prepare_saved_html(
    *,
    html_text: str,
    page_url: str,
    expected_resume_basename: str | None = None,
) -> dict:
    handler = resolve_handler(page_url=page_url, html_text=html_text)
    payload = handler.inspect_html(
        html_text,
        page_url=page_url,
        expected_resume_basename=expected_resume_basename,
    )
    return {
        "platform": handler.platform,
        "submission_enabled": False,
        "page_url": page_url,
        **payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_path")
    parser.add_argument("--page-url", required=True)
    parser.add_argument("--expected-resume-basename")
    parser.add_argument("--profile")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    try:
        resume_evidence = preflight_profile_resume(args.profile) if args.profile else None
        expected_resume_basename = (
            resume_evidence["basename"] if resume_evidence else args.expected_resume_basename
        )
        payload = prepare_saved_html(
            html_text=Path(args.html_path).read_text(),
            page_url=args.page_url,
            expected_resume_basename=expected_resume_basename,
        )
        if resume_evidence:
            payload["resume_preflight"] = resume_evidence
            payload["resume_verified"] = True
    except ValueError as exc:
        print(json.dumps({
            "error": str(exc),
            "page_url": args.page_url,
            "submission_enabled": False,
        }))
        return 2
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload))
    return 0 if payload.get("safe_to_prepare", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
