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


def test_lease_next_claims_available_job_and_increments_attempt_count(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )

    leased = queue.lease_next(now="2026-08-24T17:20:00+00:00", lease_seconds=300)

    assert leased is not None
    assert leased.state == "leased"
    assert leased.attempt_count == 1
    assert leased.lease_expires_at == "2026-08-24T17:25:00+00:00"
    assert queue.lease_next(now="2026-08-24T17:20:01+00:00", lease_seconds=300) is None


def test_finish_lease_retry_applies_backoff_and_preserves_error_detail(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )
    queue.lease_next(now="2026-08-24T17:20:00+00:00", lease_seconds=300)

    retried = queue.finish_lease(
        job.id,
        outcome="retry",
        now="2026-08-24T17:21:00+00:00",
        retry_seconds=600,
        error="temporary browser disconnect",
    )

    assert retried.state == "discovered"
    assert retried.attempt_count == 1
    assert retried.available_at == "2026-08-24T17:31:00+00:00"
    assert retried.last_error == "temporary browser disconnect"
    assert queue.lease_next(now="2026-08-24T17:30:59+00:00", lease_seconds=300) is None


def test_lease_next_recovers_stale_lease_after_expiration(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )

    first = queue.lease_next(now="2026-08-24T17:20:00+00:00", lease_seconds=300)
    recovered = queue.lease_next(now="2026-08-24T17:25:01+00:00", lease_seconds=120)

    assert first is not None
    assert recovered is not None
    assert recovered.id == job.id
    assert recovered.state == "leased"
    assert recovered.attempt_count == 2
    assert recovered.lease_expires_at == "2026-08-24T17:27:01+00:00"


def test_pending_approval_job_can_be_requeued_for_a_new_attempt(tmp_path):
    queue = app_queue.ApplicationQueue(tmp_path / "queue.db")
    job = queue.enqueue(
        company="Example",
        role="Software Engineer Intern",
        url="https://jobs.example.com/123",
        ats_platform="Greenhouse",
    )
    queue.lease_next(now="2026-08-24T17:20:00+00:00", lease_seconds=300)
    blocked = queue.finish_lease(
        job.id,
        outcome="pending_approval",
        now="2026-08-24T17:21:00+00:00",
        error="awaiting Discord approval",
    )

    requeued = queue.transition(job.id, "discovered")
    leased_again = queue.lease_next(now="2026-08-24T17:22:00+00:00", lease_seconds=120)

    assert blocked.state == "pending_approval"
    assert blocked.last_error == "awaiting Discord approval"
    assert requeued.state == "discovered"
    assert leased_again is not None
    assert leased_again.id == job.id
    assert leased_again.attempt_count == 2
