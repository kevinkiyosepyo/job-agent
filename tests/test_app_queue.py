from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app_queue


def test_enqueue_job_is_idempotent_for_same_normalized_url(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")

    first = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123?utm_source=linkedin",
        ats_platform="Greenhouse",
    )
    second = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123/",
        ats_platform="Greenhouse",
    )

    assert first.id == second.id
    assert queue.list_jobs() == [first]


def test_transition_to_next_state_is_idempotent_when_repeated(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )

    first = queue.transition(job.id, "prepared")
    second = queue.transition(job.id, "prepared")

    assert first == second
    assert second.state == "prepared"


def test_transition_rejects_skipping_required_states(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )

    with pytest.raises(ValueError, match="Invalid transition"):
        queue.transition(job.id, "applied")
