"""Bounded exact-target executor for verification-first browser actions.

The executor is transport-agnostic so its page seam can be backed by a scoped CDP
binding. It checks the live target identity and URL immediately before mutation,
then delegates to the existing action contracts for post-action read-back.
"""
from __future__ import annotations

from typing import Protocol

import browser_actions


class ExactTargetTextPage(Protocol):
    target_id: str

    def read_only_snapshot(self) -> dict[str, object]: ...

    def replace_text(self, selector: str, value: str) -> None: ...

    def read_value(self, selector: str) -> str: ...


class StaleTargetError(ValueError):
    """Raised before mutation when the bound page identity or URL changed."""


class CDPPageExecutor:
    """Run bounded browser actions only after exact live-target verification."""

    def __init__(self, page: ExactTargetTextPage) -> None:
        self._page = page

    def _verify_target(self, target_id: str, expected_url: str) -> str:
        snapshot = self._page.read_only_snapshot()
        if snapshot.get("read_only") is not True:
            raise StaleTargetError("trusted read-only target snapshot is required before action")
        actual_target_id = snapshot.get("target_id")
        actual_url = snapshot.get("url")
        if actual_target_id != target_id:
            raise StaleTargetError("target ID changed before action")
        if actual_url != expected_url:
            raise StaleTargetError("target URL changed before action")
        return expected_url

    def replace_text(
        self, *, target_id: str, expected_url: str, selector: str, value: str
    ) -> dict[str, object]:
        """Replace text once after target read-back, returning action evidence."""
        target_url = self._verify_target(target_id, expected_url)
        evidence = browser_actions.replace_text(self._page, selector, value)
        return {**evidence, "target_id": target_id, "target_url": target_url}
