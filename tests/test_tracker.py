from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tracker


def test_duplicate_normalizes_tracking_parameters_and_trailing_slash():
    rows = [{
        "Company Name": "Example",
        "Role": "Software Engineer Intern",
        "Link to Job Req": "https://jobs.example.com/123/?utm_source=linkedin",
    }]
    hit = tracker.duplicate(
        rows,
        "Different Display Name",
        "Different Role",
        "https://jobs.example.com/123?source=search",
    )
    assert hit is rows[0]


def test_append_verified_reloads_tracker_and_requires_exact_row(monkeypatch):
    values = ["Example", "Discovered", "Software Engineer Intern", "", "", "https://example.com/job/1", "N/A", "test"]
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updates": {"updatedRows": 1}})
    monkeypatch.setattr(tracker, "fetch_rows", lambda: [dict(zip(tracker.HEADERS, values))])

    result = tracker.append_verified(values)

    assert result["verified"] is True
    assert result["row"]["Company Name"] == "Example"


def test_append_verified_fails_if_readback_does_not_contain_row(monkeypatch):
    monkeypatch.setattr(tracker, "append_via_api", lambda row: {"updates": {"updatedRows": 1}})
    monkeypatch.setattr(tracker, "fetch_rows", lambda: [])

    with pytest.raises(RuntimeError, match="read-back verification"):
        tracker.append_verified(["Example", "Discovered", "Role", "", "", "https://example.com/1", "N/A", ""])
