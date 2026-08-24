from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import orchestrator


def test_dry_run_orchestrates_scan_route_queue_and_audit(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_text("fixture resume")
    profile_path.write_text(
        json.dumps(
            {
                "name": {"full": "Test User"},
                "contact": {"email": "test@example.com", "phone": "555-1111"},
                "resume": {"primary": str(resume_path)},
                "preferences": {"target_roles": ["Software Engineer Intern"]},
            }
        )
    )

    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "company": "Example",
                    "role": "Software Engineer Intern",
                    "url": "https://job-boards.greenhouse.io/example/jobs/1?utm_source=linkedin",
                    "salary": "$40/hr",
                },
                {
                    "company": "Google",
                    "role": "Software Engineer Intern",
                    "url": "https://careers.google.com/jobs/results/2",
                },
            ]
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    output_path = tmp_path / "orchestrator-report.json"
    exit_code = orchestrator.main(
        [
            str(candidates_path),
            "--profile",
            str(profile_path),
            "--output",
            str(output_path),
            "--queue-db",
            str(tmp_path / "queue.sqlite3"),
            "--audit-log",
            str(tmp_path / "audit.jsonl"),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text())
    assert payload["mode"] == "dry_run"
    assert payload["scan"]["new"] == 2
    assert payload["plan"]["counts"] == {
        "greenhouse": 1,
        "workday": 0,
        "unsupported": 0,
        "manual_only": 1,
    }
    assert payload["queue"]["count"] == 1
    queued_job = payload["queue"]["jobs"][0]
    assert queued_job["company"] == "Example"
    assert queued_job["state"] == "discovered"

    audit_lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
    assert len(audit_lines) == 1
    audit_entry = json.loads(audit_lines[0])
    assert audit_entry["event"] == "dry_run_completed"
    assert audit_entry["payload"]["profile"]["contact"]["email"] == "[REDACTED]"
    assert audit_entry["payload"]["profile"]["resume"] == "[REDACTED]"


def test_main_exits_without_side_effects_when_lock_is_already_held(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_text("fixture resume")
    profile_path.write_text(
        json.dumps(
            {
                "name": {"full": "Test User"},
                "contact": {"email": "test@example.com", "phone": "555-1111"},
                "resume": {"primary": str(resume_path)},
                "preferences": {"target_roles": ["Software Engineer Intern"]},
            }
        )
    )
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "company": "Example",
                    "role": "Software Engineer Intern",
                    "url": "https://job-boards.greenhouse.io/example/jobs/1",
                }
            ]
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    lock_path = tmp_path / "runtime" / "orchestrator.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with orchestrator.RunLock(lock_path):
        with pytest.raises(SystemExit, match="Another job-agent run is already active"):
            orchestrator.main(
                [
                    str(candidates_path),
                    "--profile",
                    str(profile_path),
                    "--output",
                    str(tmp_path / "orchestrator-report.json"),
                    "--queue-db",
                    str(tmp_path / "queue.sqlite3"),
                    "--audit-log",
                    str(tmp_path / "audit.jsonl"),
                    "--lock-path",
                    str(lock_path),
                ]
            )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


def _write_valid_profile_and_candidates(tmp_path: Path) -> tuple[Path, Path]:
    profile_path = tmp_path / "profile.json"
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_text("fixture resume")
    profile_path.write_text(
        json.dumps(
            {
                "name": {"full": "Test User"},
                "contact": {"email": "test@example.com", "phone": "555-1111"},
                "resume": {"primary": str(resume_path)},
                "preferences": {"target_roles": ["Software Engineer Intern"]},
            }
        )
    )
    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "company": "Example",
                    "role": "Software Engineer Intern",
                    "url": "https://job-boards.greenhouse.io/example/jobs/1",
                }
            ]
        )
    )
    return profile_path, candidates_path



def test_main_fails_closed_when_source_report_is_not_healthy(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "partial_error",
                "failures": [{"source": "greenhouse", "token": "example", "error": "timeout"}],
                "warning": "One configured source failed",
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Source health check failed: partial_error"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_with_stable_reason_when_source_report_is_malformed_json(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text("{not valid json")

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_json"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_with_stable_reason_when_source_report_omits_health_status(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(json.dumps({"source_runs": []}))

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: missing_source_health_status"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_omits_source_runs(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_contains_malformed_source_run_entry(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": None}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



@pytest.mark.parametrize("missing_key", ["freshness_summary", "freshness_buckets"])
def test_main_fails_closed_when_healthy_source_report_omits_required_freshness_artifact(
    tmp_path, monkeypatch, missing_key
):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    report = {
        "source_health_status": "healthy",
        "failures": [],
        "source_runs": [
            {
                "source": "greenhouse",
                "token": "fresh-co",
                "status": "ok",
                "candidates": 1,
            }
        ],
        "freshness_summary": {
            "total_runs": 1,
            "healthy_runs": 1,
            "stale_runs": 0,
            "freshness_unknown_runs": 0,
            "error_runs": 0,
        },
        "freshness_buckets": {
            "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
            "stale": [],
            "freshness_unknown": [],
            "error": [],
        },
    }
    report.pop(missing_key)
    source_report_path.write_text(json.dumps(report))

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_with_stable_reason_when_source_report_path_is_missing(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "missing-sources-report.json"

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: unreadable"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_with_stable_reason_when_source_report_status_is_not_a_string(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(json.dumps({"source_health_status": ["healthy"]}))

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_source_health_status"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )



def test_main_fails_closed_when_healthy_source_report_contains_failures(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [
                    {
                        "source": "greenhouse",
                        "token": "broken-co",
                        "error": "timeout",
                    }
                ],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "green-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "green-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_contains_non_ok_source_run(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "stale-co",
                        "status": "ok",
                        "candidates": 1,
                        "stale_result": True,
                        "warning": "Newest posting timestamp is older than 30 days",
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 0,
                    "stale_runs": 1,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [],
                    "stale": [{"source": "greenhouse", "token": "stale-co"}],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_has_contradictory_freshness_summary(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 0,
                    "stale_runs": 1,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


def test_main_fails_closed_when_healthy_source_report_has_contradictory_freshness_buckets(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_buckets": {
                    "healthy": [],
                    "stale": [{"source": "greenhouse", "token": "fresh-co"}],
                    "freshness_unknown": [],
                    "error": [],
                },
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_duplicates_source_run_identity(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    },
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    },
                ],
                "freshness_summary": {
                    "total_runs": 2,
                    "healthy_runs": 2,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [
                        {"source": "greenhouse", "token": "fresh-co"},
                        {"source": "greenhouse", "token": "fresh-co"},
                    ],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_contains_malformed_freshness_bucket_entry(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": None}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()



def test_main_fails_closed_when_healthy_source_report_contains_malformed_freshness_summary_entry(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": "1",
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


def test_main_fails_closed_when_healthy_source_report_contains_malformed_failure_entry(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "failures": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "error": None,
                    }
                ],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


def test_main_fails_closed_when_healthy_source_report_sets_top_level_stale_result(tmp_path, monkeypatch):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "stale_result": True,
                "warning": "Configured sources look stale despite healthy status",
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: inconsistent_source_health"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [("stale_result", "yes"), ("freshness_unknown", "yes")],
)
def test_main_fails_closed_when_healthy_source_report_has_non_boolean_top_level_freshness_flag(
    tmp_path, monkeypatch, field_name, field_value
):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    report = {
        "source_health_status": "healthy",
        "failures": [],
        "source_runs": [
            {
                "source": "greenhouse",
                "token": "fresh-co",
                "status": "ok",
                "candidates": 1,
            }
        ],
        "freshness_summary": {
            "total_runs": 1,
            "healthy_runs": 1,
            "stale_runs": 0,
            "freshness_unknown_runs": 0,
            "error_runs": 0,
        },
        "freshness_buckets": {
            "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
            "stale": [],
            "freshness_unknown": [],
            "error": [],
        },
    }
    report[field_name] = field_value
    source_report_path.write_text(json.dumps(report))

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()


def test_main_fails_closed_when_healthy_source_report_has_non_string_top_level_warning(
    tmp_path, monkeypatch
):
    profile_path, candidates_path = _write_valid_profile_and_candidates(tmp_path)
    source_report_path = tmp_path / "sources-report.json"
    source_report_path.write_text(
        json.dumps(
            {
                "source_health_status": "healthy",
                "warning": ["unexpected", "list"],
                "failures": [],
                "source_runs": [
                    {
                        "source": "greenhouse",
                        "token": "fresh-co",
                        "status": "ok",
                        "candidates": 1,
                    }
                ],
                "freshness_summary": {
                    "total_runs": 1,
                    "healthy_runs": 1,
                    "stale_runs": 0,
                    "freshness_unknown_runs": 0,
                    "error_runs": 0,
                },
                "freshness_buckets": {
                    "healthy": [{"source": "greenhouse", "token": "fresh-co"}],
                    "stale": [],
                    "freshness_unknown": [],
                    "error": [],
                },
            }
        )
    )

    monkeypatch.setattr(orchestrator.scanner, "tracker_duplicate", lambda company, role, url: False)

    with pytest.raises(SystemExit, match="Invalid source report: invalid_schema"):
        orchestrator.main(
            [
                str(candidates_path),
                "--profile",
                str(profile_path),
                "--output",
                str(tmp_path / "orchestrator-report.json"),
                "--queue-db",
                str(tmp_path / "queue.sqlite3"),
                "--audit-log",
                str(tmp_path / "audit.jsonl"),
                "--source-report",
                str(source_report_path),
            ]
        )

    assert not (tmp_path / "orchestrator-report.json").exists()
    assert not (tmp_path / "audit.jsonl").exists()
    assert not (tmp_path / "queue.sqlite3").exists()
