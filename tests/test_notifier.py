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


def test_target_uses_environment_override(monkeypatch):
    monkeypatch.setenv("JOB_AGENT_DISCORD_TARGET", "discord:123")
    assert notifier.default_target() == "discord:123"
