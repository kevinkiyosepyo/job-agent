from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sources


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_greenhouse_adapter_returns_active_internship_candidates_from_public_api():
    calls: list[str] = []

    def fake_open(url: str, timeout: float):
        calls.append(url)
        assert timeout == 15.0
        return FakeResponse(
            {
                "jobs": [
                    {
                        "id": 101,
                        "title": "Software Engineer Intern",
                        "absolute_url": "https://job-boards.greenhouse.io/example/jobs/101",
                        "location": {"name": "San Francisco, CA"},
                        "updated_at": "2026-08-23T18:00:00Z",
                    },
                    {
                        "id": 102,
                        "title": "Senior Software Engineer",
                        "absolute_url": "https://job-boards.greenhouse.io/example/jobs/102",
                        "location": {"name": "Remote"},
                        "updated_at": "2026-08-23T18:00:00Z",
                    },
                ]
            }
        )

    jobs = sources.fetch_greenhouse_jobs("example", opener=fake_open)

    assert calls == ["https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"]
    assert jobs == [
        {
            "company": "Example",
            "role": "Software Engineer Intern",
            "url": "https://job-boards.greenhouse.io/example/jobs/101",
            "location": "San Francisco, CA",
            "source": "Greenhouse public API",
            "updated_at": "2026-08-23T18:00:00Z",
        }
    ]



def test_lever_adapter_retries_transient_failures_and_returns_internships_only():
    attempts = {"count": 0}

    def flaky_open(url: str, timeout: float):
        attempts["count"] += 1
        assert url == "https://api.lever.co/v0/postings/example?mode=json"
        assert timeout == 15.0
        if attempts["count"] < 3:
            raise TimeoutError("temporary network issue")
        return FakeResponse(
            [
                {
                    "text": "Data Scientist Intern",
                    "hostedUrl": "https://jobs.lever.co/example/1",
                    "categories": {"location": "San Diego, CA", "team": "Data"},
                    "createdAt": 1787517600000,
                },
                {
                    "text": "Senior Data Scientist",
                    "hostedUrl": "https://jobs.lever.co/example/2",
                    "categories": {"location": "Remote", "team": "Data"},
                    "createdAt": 1787517600000,
                },
            ]
        )

    jobs = sources.fetch_lever_jobs("example", opener=flaky_open, attempts=3)

    assert attempts["count"] == 3
    assert jobs == [
        {
            "company": "Example",
            "role": "Data Scientist Intern",
            "url": "https://jobs.lever.co/example/1",
            "location": "San Diego, CA",
            "team": "Data",
            "source": "Lever public API",
            "created_at": 1787517600000,
        }
    ]
