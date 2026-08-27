import json

import production_operator


def _release_evidence() -> dict:
    return {
        "schema_version": 1,
        "mode": "sanitized_local_release",
        "queue": {
            "heading": "Unified live-production CLI queue — completed",
            "tasks_completed": 10,
            "ordered_task_commits": True,
        },
        "verification": {
            "focused_tdd_passed": True,
            "full_suite": {
                "command": "python -m pytest tests -q",
                "passed": 306,
            },
            "local_chrome": {
                "passed": True,
                "sanitized_fixture_only": True,
                "submit_count": 1,
                "replay_denied": True,
            },
            "normal_chrome_preflight": {
                "passed": True,
                "read_only": True,
                "exact_target_attached": True,
                "content_unchanged": True,
                "submission_enabled": False,
            },
            "git_diff_check": True,
            "forbidden_executable_source_matches": [],
            "clean_worktree": True,
        },
        "documentation": {
            "readme_updated": True,
            "operations_updated": True,
            "job_application_skill_updated": True,
        },
        "safety": {
            "credentials_accessed": False,
            "external_message_sent": False,
            "live_tracker_mutated": False,
            "production_ats_accessed": False,
            "real_application_authorized": False,
            "real_application_submitted": False,
            "sanitized_fixture_only": True,
        },
    }


def test_live_release_audit_requires_complete_sanitized_evidence_and_never_enables_real_live(
    tmp_path, capsys
):
    evidence_path = tmp_path / "release-evidence.json"
    evidence = _release_evidence()
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    assert production_operator.main(
        ["live", "release-audit", "--evidence", str(evidence_path)]
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "checks_passed": True,
        "commit_external_enabled": False,
        "real_application_authorized": False,
        "real_live_enabled": False,
        "status": "ready_for_manual_live_authorization_review",
    }

    evidence["verification"]["normal_chrome_preflight"]["read_only"] = False
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    assert production_operator.main(
        ["live", "release-audit", "--evidence", str(evidence_path)]
    ) == 1
    blocked = json.loads(capsys.readouterr().out)
    assert blocked["checks_passed"] is False
    assert blocked["status"] == "not_ready"
    assert blocked["real_live_enabled"] is False
    assert blocked["commit_external_enabled"] is False
    assert blocked["real_application_authorized"] is False

    evidence["queue"] = [{}]
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    assert production_operator.main(
        ["live", "release-audit", "--evidence", str(evidence_path)]
    ) == 1
    malformed = json.loads(capsys.readouterr().out)
    assert malformed["checks_passed"] is False
    assert malformed["status"] == "not_ready"
