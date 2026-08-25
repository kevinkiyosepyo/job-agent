from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import browser_actions


class InMemoryPage:
    """Deterministic page seam used to verify browser action contracts."""

    def __init__(self) -> None:
        self.values = {"#first-name": "Old value"}
        self.checked: dict[str, bool] = {}
        self.operations: list[tuple[str, str, str]] = []

    def replace_text(self, selector: str, value: str) -> None:
        self.operations.append(("replace_text", selector, value))
        self.values[selector] = value

    def read_value(self, selector: str) -> str:
        return self.values[selector]

    def select_option(self, selector: str, value: str) -> None:
        self.operations.append(("select_option", selector, value))
        self.values[selector] = value

    def read_selected_option(self, selector: str) -> str:
        return self.values[selector]

    def set_checked(self, selector: str, checked: bool) -> None:
        self.operations.append(("set_checked", selector, str(checked)))
        self.checked[selector] = checked

    def read_checked(self, selector: str) -> bool:
        return self.checked[selector]

    def cdp_upload(self, selector: str, path: str) -> None:
        self.operations.append(("cdp_upload", selector, path))
        self.values[selector] = Path(path).name

    def read_uploaded_filename(self, selector: str) -> str:
        return self.values[selector]

    def scroll_into_view(self, selector: str) -> None:
        self.operations.append(("scroll_into_view", selector, ""))

    def click(self, selector: str) -> None:
        self.operations.append(("click", selector, ""))
        self.values[selector] = "clicked"

    def read_post_click_state(self, selector: str) -> str:
        return self.values[selector]

    def submit(self, selector: str) -> None:
        self.operations.append(("submit", selector, ""))
        self.values["#confirmation"] = "Application received"

    def read_confirmation(self) -> str:
        return self.values["#confirmation"]


def test_replace_text_returns_exact_post_action_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.replace_text(page, "#first-name", "Kevin")

    assert page.operations == [("replace_text", "#first-name", "Kevin")]
    assert evidence == {
        "action": "replace_text",
        "selector": "#first-name",
        "expected": "Kevin",
        "actual": "Kevin",
        "verified": True,
    }


def test_native_select_returns_selected_option_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.native_select(page, "#country", "United States")

    assert page.operations == [("select_option", "#country", "United States")]
    assert evidence == {
        "action": "native_select",
        "selector": "#country",
        "expected": "United States",
        "actual": "United States",
        "verified": True,
    }


def test_set_checked_returns_checked_state_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.set_checked(page, "#consent", True)

    assert page.operations == [("set_checked", "#consent", "True")]
    assert evidence == {
        "action": "set_checked",
        "selector": "#consent",
        "expected": True,
        "actual": True,
        "verified": True,
    }


def test_cdp_upload_returns_attached_file_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.cdp_upload(
        page, "#resume-upload", "/safe/Resume.pdf"
    )

    assert page.operations == [("cdp_upload", "#resume-upload", "/safe/Resume.pdf")]
    assert evidence == {
        "action": "cdp_upload",
        "selector": "#resume-upload",
        "expected": "Resume.pdf",
        "actual": "Resume.pdf",
        "verified": True,
    }


def test_scroll_and_click_returns_post_click_state_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.scroll_and_click(page, "#continue", "clicked")

    assert page.operations == [
        ("scroll_into_view", "#continue", ""),
        ("click", "#continue", ""),
    ]
    assert evidence == {
        "action": "scroll_and_click",
        "selector": "#continue",
        "expected": "clicked",
        "actual": "clicked",
        "verified": True,
    }


def test_submit_and_confirm_returns_explicit_confirmation_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.submit_and_confirm(page, "#submit", "Application received")

    assert page.operations == [("submit", "#submit", "")]
    assert evidence == {
        "action": "submit_and_confirm",
        "selector": "#submit",
        "expected": "Application received",
        "actual": "Application received",
        "verified": True,
    }
