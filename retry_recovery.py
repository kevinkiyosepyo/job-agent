"""Bounded recovery policy that never replays a potentially completed action."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class RecoverableAttemptError(Exception):
    """An action outcome that requires inspection instead of blind replay."""


def execute_once_with_inspected_recovery(
    normal_attempt: Callable[[], dict[str, object]],
    inspect_recovery: Callable[[str], dict[str, Any]],
) -> dict[str, object]:
    """Attempt once, then inspect once; a confirmed result is never replayed."""
    try:
        normal_attempt()
    except RecoverableAttemptError as error:
        inspection = inspect_recovery(str(error))
        if inspection.get("completed") is True:
            return {
                "status": "recovered",
                "normal_attempts": 1,
                "recovery_inspections": 1,
                "confirmation": inspection.get("confirmation"),
            }
        return {
            "status": "blocked",
            "blocker": inspection.get("reason", "recovery inspection did not confirm completion"),
            "normal_attempts": 1,
            "recovery_inspections": 1,
        }
    return {
        "status": "completed",
        "normal_attempts": 1,
        "recovery_inspections": 0,
    }
