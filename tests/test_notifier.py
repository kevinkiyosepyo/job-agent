from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import notifier


def test_build_message_contains_state_and_identity():
    message = notifier.build_message(
        "captcha",
        company="Example Co",
        role="Data Science Intern",
        url="https://example.com/job/1",
        detail="Form is complete and waiting.",
    )
    assert "Manual CAPTCHA needed" in message
    assert "Example Co" in message
    assert "Data Science Intern" in message
    assert "https://example.com/job/1" in message


def test_applied_cli_cannot_bypass_verified_transaction(monkeypatch, capsys):
    import json
    import pytest
    monkeypatch.setattr(sys, "argv", ["notifier.py", "applied", "--company", "Example"])
    monkeypatch.setattr(notifier.subprocess, "run", lambda *args, **kwargs: pytest.fail("unverified direct send"))
    assert notifier.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["notification_state"] == "not_started"
    assert "production_operator" in report["next_action"]


def test_target_uses_environment_override(monkeypatch):
    monkeypatch.setenv("JOB_AGENT_DISCORD_TARGET", "discord:123")
    assert notifier.default_target() == "discord:123"
