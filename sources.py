#!/usr/bin/env python3
"""Public job source adapters with deterministic normalization."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen


DEFAULT_TIMEOUT = 15.0
DEFAULT_ATTEMPTS = 3
STALE_POSTING_DAYS = 30


class ResponseLike(Protocol):
    def read(self) -> bytes: ...
    def __enter__(self) -> "ResponseLike": ...
    def __exit__(self, exc_type, exc, tb) -> bool | None: ...


OpenUrl = Callable[[str, float], ResponseLike]


def _default_open(url: str, timeout: float) -> ResponseLike:
    return urlopen(url, timeout=timeout)


def _company_name(token: str) -> str:
    return token.replace("-", " ").title()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    keep = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "trk", "trackingid", "gh_src"}
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(keep), ""))


def _dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for job in sorted(jobs, key=lambda item: (item.get("company", ""), item.get("role", ""), _normalize_url(item.get("url", "")))):
        normalized_url = _normalize_url(job.get("url", ""))
        if not normalized_url or normalized_url in seen:
            continue
        seen.add(normalized_url)
        unique.append({**job, "url": normalized_url})
    return unique


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return None


def _latest_posting_at(jobs: list[dict]) -> str | None:
    timestamps = [
        parsed
        for job in jobs
        for parsed in (_parse_timestamp(job.get("updated_at")), _parse_timestamp(job.get("created_at")))
        if parsed is not None
    ]
    if not timestamps:
        return None
    return max(timestamps).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stale_warning(latest_posting_at: str | None) -> str | None:
    if latest_posting_at is None:
        return None
    latest_posting_dt = _parse_timestamp(latest_posting_at)
    assert latest_posting_dt is not None
    if latest_posting_dt <= _utcnow() - timedelta(days=STALE_POSTING_DAYS):
        return f"Newest posting timestamp is older than {STALE_POSTING_DAYS} days"
    return None


def _missing_timestamp_warning(jobs: list[dict]) -> str | None:
    if jobs and _latest_posting_at(jobs) is None:
        return "No posting timestamps available; freshness unknown"
    return None


def _load_json(url: str, *, opener: OpenUrl, timeout: float = DEFAULT_TIMEOUT, attempts: int = DEFAULT_ATTEMPTS) -> Any:
    last_error: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            with opener(url, timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            last_error = exc
    assert last_error is not None
    raise RuntimeError(f"Failed to fetch {url} after {max(1, attempts)} attempts") from last_error


def fetch_greenhouse_jobs(board_token: str, *, opener: OpenUrl = _default_open, attempts: int = DEFAULT_ATTEMPTS) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
    payload = _load_json(url, opener=opener, attempts=attempts)

    jobs: list[dict] = []
    for job in payload.get("jobs", []):
        role = (job.get("title") or "").strip()
        if "intern" not in role.casefold():
            continue
        jobs.append(
            {
                "company": _company_name(board_token),
                "role": role,
                "url": job.get("absolute_url", "").strip(),
                "location": (job.get("location") or {}).get("name", "").strip(),
                "source": "Greenhouse public API",
                "updated_at": (job.get("updated_at") or "").strip(),
            }
        )
    return jobs


def fetch_lever_jobs(company_token: str, *, opener: OpenUrl = _default_open, attempts: int = DEFAULT_ATTEMPTS) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"
    payload = _load_json(url, opener=opener, attempts=attempts)

    jobs: list[dict] = []
    for job in payload:
        role = (job.get("text") or "").strip()
        if "intern" not in role.casefold():
            continue
        categories = job.get("categories") or {}
        jobs.append(
            {
                "company": _company_name(company_token),
                "role": role,
                "url": job.get("hostedUrl", "").strip(),
                "location": (categories.get("location") or "").strip(),
                "team": (categories.get("team") or "").strip(),
                "source": "Lever public API",
                "created_at": job.get("createdAt"),
            }
        )
    return jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--greenhouse", action="append", default=[], help="Greenhouse board token")
    parser.add_argument("--lever", action="append", default=[], help="Lever company token")
    parser.add_argument("--output", required=True, help="Output JSON array path")
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    if not args.greenhouse and not args.lever:
        print(
            json.dumps(
                {
                    "greenhouse_tokens": args.greenhouse,
                    "lever_tokens": args.lever,
                    "candidates": 0,
                    "failures": [],
                    "output": str(output_path),
                    "error": "At least one --greenhouse or --lever token is required",
                }
            )
        )
        return 2

    jobs: list[dict] = []
    failures: list[dict[str, str]] = []
    source_runs: list[dict[str, str | int]] = []
    for token in args.greenhouse:
        try:
            token_jobs = fetch_greenhouse_jobs(token)
            jobs.extend(token_jobs)
            run = {"source": "greenhouse", "token": token, "status": "ok", "candidates": len(token_jobs)}
            latest_posting_at = _latest_posting_at(token_jobs)
            if latest_posting_at is not None:
                run["latest_posting_at"] = latest_posting_at
                warning = _stale_warning(latest_posting_at)
                if warning is not None:
                    run["warning"] = warning
                    run["stale_result"] = True
            else:
                warning = _missing_timestamp_warning(token_jobs)
                if warning is not None:
                    run["warning"] = warning
                    run["freshness_unknown"] = True
            source_runs.append(run)
        except Exception as exc:
            failures.append({"source": "greenhouse", "token": token, "error": str(exc)})
            source_runs.append({"source": "greenhouse", "token": token, "status": "error", "error": str(exc), "candidates": 0})
    for token in args.lever:
        try:
            token_jobs = fetch_lever_jobs(token)
            jobs.extend(token_jobs)
            run = {"source": "lever", "token": token, "status": "ok", "candidates": len(token_jobs)}
            latest_posting_at = _latest_posting_at(token_jobs)
            if latest_posting_at is not None:
                run["latest_posting_at"] = latest_posting_at
                warning = _stale_warning(latest_posting_at)
                if warning is not None:
                    run["warning"] = warning
                    run["stale_result"] = True
            else:
                warning = _missing_timestamp_warning(token_jobs)
                if warning is not None:
                    run["warning"] = warning
                    run["freshness_unknown"] = True
            source_runs.append(run)
        except Exception as exc:
            failures.append({"source": "lever", "token": token, "error": str(exc)})
            source_runs.append({"source": "lever", "token": token, "status": "error", "error": str(exc), "candidates": 0})

    unique_jobs = _dedupe_jobs(jobs)
    output_path.write_text(json.dumps(unique_jobs, indent=2) + "\n")
    latest_posting_at = _latest_posting_at(unique_jobs)

    result = {
        "greenhouse_tokens": args.greenhouse,
        "lever_tokens": args.lever,
        "candidates": len(unique_jobs),
        "failures": failures,
        "source_runs": source_runs,
        "output": str(output_path),
    }
    if latest_posting_at is not None:
        result["latest_posting_at"] = latest_posting_at
    if not failures and not unique_jobs:
        result["warning"] = "Configured source tokens returned zero internship candidates"
        result["stale_result"] = True
    elif not failures and latest_posting_at is not None:
        warning = _stale_warning(latest_posting_at)
        if warning is not None:
            result["warning"] = warning
            result["stale_result"] = True

    print(json.dumps(result))
    if failures:
        return 1
    if result.get("stale_result"):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
