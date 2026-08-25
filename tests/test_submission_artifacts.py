from __future__ import annotations

import copy
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


def test_reconcile_submission_delivery_uses_tracker_read_back_and_notification_delivery_results():
    artifact = submission_artifacts.build_submission_artifact(
        {
            "company": "Example Co",
            "role": "Software Engineer Intern",
            "url": "https://jobs.example.com/roles/123",
        },
        confirmation_url="https://jobs.example.com/apply/confirmation/123",
        confirmation_text="Thanks for applying. We received your application.",
    )
    tracker_result = {
        "verified": True,
        "row": {
            "Company Name": "Example Co",
            "Application Status": "Submitted - Pending Response",
            "Role": "Software Engineer Intern",
            "Salary": "",
            "Date Submitted": artifact["tracker"]["values"][4],
            "Link to Job Req": "https://jobs.example.com/roles/123",
            "Rejection Reason": "N/A",
            "Notes": artifact["tracker"]["values"][7],
        },
    }
    notification_result = {
        "delivered": True,
        "target": "discord:123",
        "read_back": {
            "message": artifact["notification"]["message"],
        },
    }

    reconciled = submission_artifacts.reconcile_submission_delivery(
        copy.deepcopy(artifact),
        tracker_result=tracker_result,
        notification_result=notification_result,
    )

    assert reconciled["tracker"]["verified"] is True
    assert reconciled["tracker"]["row"] == tracker_result["row"]
    assert reconciled["notification"] == {
        "kind": "applied",
        "message": artifact["notification"]["message"],
        "delivered": True,
        "target": "discord:123",
        "read_back": artifact["notification"]["message"],
    }
    assert reconciled["reconciliation"] == {
        "tracker_status": "Submitted - Pending Response",
        "notification_kind": "applied",
        "tracker_verified": True,
        "notification_delivered": True,
        "tracker_matches_expected": True,
        "notification_matches_expected": True,
        "consistent": True,
    }
