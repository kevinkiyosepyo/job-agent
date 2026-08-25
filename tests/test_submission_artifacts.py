from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import submission_artifacts


def test_build_submission_artifact_sanitizes_confirmation_html_and_reconciles_tracker_with_discord_message():
    job = {
        "company": "Example Co",
        "role": "Software Engineer Intern",
        "url": "https://jobs.example.com/roles/123",
        "salary": "$40/hr",
    }
    confirmation_text = """
    <main>
      <h1>Thanks for applying</h1>
      <p>We've received your application for Software Engineer Intern.</p>
      <p>Contact recruiting@example.com or call 555-111-2222.</p>
    </main>
    """

    artifact = submission_artifacts.build_submission_artifact(
        job,
        confirmation_url="https://jobs.example.com/apply/confirmation/123",
        confirmation_text=confirmation_text,
    )

    assert artifact["tracker"]["values"][0] == "Example Co"
    assert artifact["tracker"]["values"][1] == "Submitted - Pending Response"
    assert artifact["tracker"]["values"][2] == "Software Engineer Intern"
    assert artifact["notification"]["kind"] == "applied"
    assert "Application submitted" in artifact["notification"]["message"]
    assert artifact["evidence"] == {
        "confirmation_url": "https://jobs.example.com/apply/confirmation/123",
        "confirmation_excerpt": "Thanks for applying We've received your application for Software Engineer Intern. Contact [REDACTED_EMAIL] or call [REDACTED_PHONE].",
    }
    assert artifact["reconciliation"] == {
        "tracker_status": "Submitted - Pending Response",
        "notification_kind": "applied",
        "consistent": True,
    }
