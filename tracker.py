#!/usr/bin/env python3
"""Read, deduplicate, and append Kevin's job application tracker."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SHEET_ID = "1z7DTGJthLoQkjq-k5FFfkTdP3HizJCytYKvhcbKLolw"
SHEET_GID = "0"
SHEET_NAME = "Tracking Template"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={SHEET_GID}#gid={SHEET_GID}"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={SHEET_GID}"
HEADERS = [
    "Company Name", "Application Status", "Role", "Salary", "Date Submitted",
    "Link to Job Req", "Rejection Reason", "Notes",
]
LOCAL_CACHE = Path.home() / "Documents/job-agent/current-tracker.csv"
GAPI = Path.home() / ".hermes/skills/productivity/google-workspace/scripts/google_api.py"


def normalize(text: str) -> str:
    text = text.casefold()
    text = re.sub(r"\b(internship|intern|co-op|coop|summer|spring|fall|winter|20\d{2})\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_job_url(url: str) -> str:
    """Normalize tracking noise while preserving requisition identity."""
    parts = urlsplit(url.strip())
    keep = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"ref", "source", "trk", "trackingid"}
    ]
    return urlunsplit((
        parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/"),
        urlencode(keep), "",
    ))


def fetch_rows() -> list[dict[str, str]]:
    with urllib.request.urlopen(CSV_URL, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    LOCAL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CACHE.write_text(text, encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def nonempty(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if (r.get("Company Name") or "").strip()]


def duplicate(rows: list[dict[str, str]], company: str, role: str, url: str = "") -> dict[str, str] | None:
    target = (normalize(company), normalize(role))
    target_url = normalize_job_url(url) if url.strip() else ""
    for row in nonempty(rows):
        if target_url and normalize_job_url(row.get("Link to Job Req") or "") == target_url:
            return row
        if (normalize(row.get("Company Name", "")), normalize(row.get("Role", ""))) == target:
            return row
    return None


def append_via_api(values: list[str]) -> dict:
    if not (Path.home() / ".hermes/google_token.json").exists():
        raise RuntimeError(
            "Google Sheets write OAuth is not configured. Run the google-workspace setup, "
            f"or add the row manually at {SHEET_URL}."
        )
    cmd = [
        sys.executable, str(GAPI), "sheets", "append", SHEET_ID,
        f"'{SHEET_NAME}'!A:H", "--values", json.dumps([values]),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return json.loads(proc.stdout)


def append_verified(values: list[str]) -> dict:
    """Append and require the exact row to appear in a fresh read."""
    api_result = append_via_api(values)
    expected = dict(zip(HEADERS, values))
    for row in fetch_rows():
        if all((row.get(header) or "") == (expected.get(header) or "") for header in HEADERS):
            return {"verified": True, "api_result": api_result, "row": row}
    raise RuntimeError("Google Sheets append returned success but read-back verification failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary")
    check = sub.add_parser("check")
    check.add_argument("--company", required=True)
    check.add_argument("--role", required=True)
    check.add_argument("--url", default="")
    add = sub.add_parser("append")
    add.add_argument("--company", required=True)
    add.add_argument("--role", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--status", default="Discovered")
    add.add_argument("--salary", default="")
    add.add_argument("--date", default="")
    add.add_argument("--rejection", default="N/A")
    add.add_argument("--notes", default="")
    add.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = fetch_rows()
    if args.command == "summary":
        actual = nonempty(rows)
        statuses: dict[str, int] = {}
        for row in actual:
            key = row.get("Application Status", "") or "(blank)"
            statuses[key] = statuses.get(key, 0) + 1
        print(json.dumps({"sheet": SHEET_URL, "rows": len(actual), "statuses": statuses}, indent=2))
        return 0

    hit = duplicate(rows, args.company, args.role, getattr(args, "url", ""))
    if args.command == "check":
        print(json.dumps({"duplicate": bool(hit), "match": hit}, indent=2))
        return 10 if hit else 0

    if hit:
        print(json.dumps({"status": "skipped_duplicate", "match": hit}, indent=2))
        return 10
    values = [
        args.company, args.status, args.role, args.salary,
        args.date or (date.today().isoformat() if args.status.startswith("Submitted") else ""),
        args.url, args.rejection, args.notes,
    ]
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "values": values}, indent=2))
        return 0
    result = append_verified(values)
    print(json.dumps({"status": "appended_verified", "result": result, "values": values}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
