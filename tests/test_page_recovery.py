from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_recovery_journal_blocks_replay_after_uncertain_submit(tmp_path):
    import page_recovery

    journal_path = tmp_path / "page-journal.jsonl"
    page_recovery.record_page_action(
        journal_path,
        action="submit",
        evidence={"verified": False, "reason": "connection interrupted"},
    )

    result = page_recovery.resume_from_verified_page_state(journal_path)

    assert result == {
        "status": "blocked",
        "blocker": "uncertain submit requires confirmation inspection",
        "next_action": "inspect_confirmation_without_replay",
    }
