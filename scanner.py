#!/usr/bin/env python3
"""Deterministic job-candidate filter, ATS detector, and tracker deduper."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE = Path.home() / "Documents/job-agent"
TRACKER = BASE / "tracker.py"
PROFILE = BASE / "profile.json"
NOTIFIER = BASE / "notifier.py"
MAANGO = {"meta", "amazon", "apple", "netflix", "google", "microsoft"}
SUBSIDIARY_DOMAINS = {
    "amazon.jobs": "Amazon", "aws.amazon.com": "Amazon",
    "metacareers.com": "Meta", "facebook.com": "Meta", "instagram.com": "Meta",
    "jobs.apple.com": "Apple", "jobs.netflix.com": "Netflix",
    "careers.google.com": "Google", "youtube.com": "Google",
    "careers.microsoft.com": "Microsoft", "linkedin.com": "Microsoft",
}
ATS = [
    ("greenhouse.io", "Greenhouse"), ("myworkdayjobs.com", "Workday"),
    ("myworkdaysite.com", "Workday"), ("lever.co", "Lever"),
    ("ashbyhq.com", "Ashby"), ("smartrecruiters.com", "SmartRecruiters"),
    ("bamboohr.com", "BambooHR"), ("icims.com", "iCIMS"),
    ("jobvite.com", "Jobvite"), ("taleo.net", "Taleo"),
    ("successfactors.com", "SAP SuccessFactors"),
]


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    keep = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "trk", "trackingid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(keep), ""))


def detect_ats(url: str) -> str:
    low = url.casefold()
    return next((name for pattern, name in ATS if pattern in low), "Unknown")


def unique_jobs(jobs: list[dict]) -> list[dict]:
    """Keep the first candidate for each normalized official URL."""
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        key = normalize_url(job.get("url", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def maango_company(company: str, url: str) -> str | None:
    words = set(re.findall(r"[a-z0-9]+", company.casefold()))
    hit = MAANGO & words
    if hit and not words.intersection({"credit", "union", "bank"}):
        return sorted(hit)[0].title()
    host = urlsplit(url).netloc.casefold()
    for domain, parent in SUBSIDIARY_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return parent
    return None


def relevant(role: str, profile: dict) -> bool:
    low = role.casefold()
    role_terms = [x.casefold().replace(" intern", "") for x in profile["preferences"]["target_roles"]]
    target = any(term in low for term in role_terms)
    aliases = {
        "ai/ml engineer": ("ai engineer", "ml engineer", "machine learning engineer", "artificial intelligence engineer"),
    }
    if not target:
        target = any(alias in low for term in role_terms for alias in aliases.get(term, ()))
    level = any(x in low for x in ("intern", "co-op", "coop", "new grad", "entry level", "fellow"))
    senior = bool(re.search(r"\b(senior|staff|principal|lead|manager|director|vp)\b", low))
    return target and level and not senior


def tracker_duplicate(company: str, role: str, url: str) -> bool:
    proc = subprocess.run([sys.executable, str(TRACKER), "check", "--company", company,
                           "--role", role, "--url", normalize_url(url)], capture_output=True, text=True)
    if proc.returncode not in (0, 10):
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)["duplicate"]


def classify(job: dict, profile: dict) -> dict:
    company, role = job["company"].strip(), job["role"].strip()
    url = normalize_url(job["url"])
    parent = maango_company(company, url)
    return {**job, "company": company, "role": role, "url": url,
            "ats_platform": detect_ats(url), "relevant": relevant(role, profile),
            "duplicate": tracker_duplicate(company, role, url),
            "manual_only": bool(parent), "maango_parent": parent}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input", nargs="?", help="JSON array file; omit for stdin")
    p.add_argument("--notify-maango", action="store_true")
    p.add_argument("--output", default=str(BASE / "scan-results.json"))
    args = p.parse_args()
    profile = json.loads(PROFILE.read_text())
    text = Path(args.input).read_text() if args.input else sys.stdin.read()
    jobs = unique_jobs(json.loads(text))
    results = [classify(job, profile) for job in jobs]
    new = [x for x in results if x["relevant"] and not x["duplicate"]]
    manual = [x for x in new if x["manual_only"]]
    queue = [x for x in new if not x["manual_only"]]
    if args.notify_maango:
        for job in manual:
            subprocess.run([sys.executable, str(NOTIFIER), "maango", "--company", job["company"],
                            "--role", job["role"], "--url", job["url"],
                            "--detail", "Found by the job scanner. Kevin should review and apply manually."], check=True)
    payload = {"scanned": len(results), "new": len(new), "manual_only": manual,
               "auto_apply_queue": queue, "all_results": results}
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
