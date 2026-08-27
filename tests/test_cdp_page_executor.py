from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeCDPPage:
    def __init__(self, *, target_id: str, url: str) -> None:
        self.target_id = target_id
        self.url = url
        self.values = {"#first-name": "Old value"}
        self.operations: list[tuple[str, str, str]] = []

    def read_only_snapshot(self) -> dict[str, object]:
        return {"target_id": self.target_id, "url": self.url, "read_only": True}

    def replace_text(self, selector: str, value: str) -> None:
        self.operations.append(("replace_text", selector, value))
        self.values[selector] = value

    def read_value(self, selector: str) -> str:
        return self.values[selector]


def test_executor_replaces_text_only_after_exact_target_readback():
    import cdp_page_executor

    page = FakeCDPPage(target_id="page-42", url="https://careers.example.test/apply")
    executor = cdp_page_executor.CDPPageExecutor(page)

    evidence = executor.replace_text(
        target_id="page-42",
        expected_url="https://careers.example.test/apply",
        selector="#first-name",
        value="Kevin",
    )

    assert page.operations == [("replace_text", "#first-name", "Kevin")]
    assert evidence == {
        "action": "replace_text",
        "selector": "#first-name",
        "expected": "Kevin",
        "actual": "Kevin",
        "verified": True,
        "target_id": "page-42",
        "target_url": "https://careers.example.test/apply",
    }


def test_executor_rejects_untrusted_snapshot_before_any_mutation():
    import cdp_page_executor

    page = FakeCDPPage(target_id="page-42", url="https://careers.example.test/apply")
    page.read_only_snapshot = lambda: {  # type: ignore[method-assign]
        "target_id": "page-42",
        "url": "https://careers.example.test/apply",
        "read_only": False,
    }
    executor = cdp_page_executor.CDPPageExecutor(page)

    with pytest.raises(cdp_page_executor.StaleTargetError, match="trusted read-only"):
        executor.replace_text(
            target_id="page-42",
            expected_url="https://careers.example.test/apply",
            selector="#first-name",
            value="Kevin",
        )

    assert page.operations == []
