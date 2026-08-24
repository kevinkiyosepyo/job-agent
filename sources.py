#!/usr/bin/env python3
"""Public job source adapters with deterministic normalization."""
from __future__ import annotations

import json
from typing import Any, Callable, Protocol
from urllib.request import urlopen


DEFAULT_TIMEOUT = 15.0
DEFAULT_ATTEMPTS = 3


class ResponseLike(Protocol):
    def read(self) -> bytes: ...
    def __enter__(self) -> "ResponseLike": ...
    def __exit__(self, exc_type, exc, tb) -> bool | None: ...


OpenUrl = Callable[[str, float], ResponseLike]


def _default_open(url: str, timeout: float) -> ResponseLike:
    return urlopen(url, timeout=timeout)


def _company_name(token: str) -> str:
    return token.replace("-", " ").title()


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
