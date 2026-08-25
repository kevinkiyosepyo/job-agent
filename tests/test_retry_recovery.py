from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import retry_recovery


def test_execute_once_uses_one_inspection_to_recover_without_replaying_normal_attempt():
    calls: list[str] = []

    def normal_attempt() -> dict[str, object]:
        calls.append("normal")
        raise retry_recovery.RecoverableAttemptError("connection interrupted")

    def inspect_recovery(error: str) -> dict[str, object]:
        calls.append(f"inspect:{error}")
        return {"completed": True, "confirmation": "Application received"}

    result = retry_recovery.execute_once_with_inspected_recovery(
        normal_attempt,
        inspect_recovery,
    )

    assert calls == ["normal", "inspect:connection interrupted"]
    assert result == {
        "status": "recovered",
        "normal_attempts": 1,
        "recovery_inspections": 1,
        "confirmation": "Application received",
    }


def test_execute_once_returns_stable_blocker_after_nonconfirming_inspection():
    calls: list[str] = []

    def normal_attempt() -> dict[str, object]:
        calls.append("normal")
        raise retry_recovery.RecoverableAttemptError("connection interrupted")

    def inspect_recovery(error: str) -> dict[str, object]:
        calls.append(f"inspect:{error}")
        return {"completed": False, "reason": "confirmation not found"}

    result = retry_recovery.execute_once_with_inspected_recovery(
        normal_attempt,
        inspect_recovery,
    )

    assert calls == ["normal", "inspect:connection interrupted"]
    assert result == {
        "status": "blocked",
        "blocker": "confirmation not found",
        "normal_attempts": 1,
        "recovery_inspections": 1,
    }
