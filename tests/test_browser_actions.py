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

    def react_select_exact(self, selector: str, search_text: str, exact_option: str) -> None:
        self.operations.append(("react_select_exact", selector, search_text))
        self.values[selector] = exact_option

    def read_react_selected_option(self, selector: str) -> str:
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
        return self.values.get(selector, "")

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


def test_replace_tel_local_digits_verifies_only_the_local_digits_after_formatting():
    class FormattedTelephonePage(InMemoryPage):
        def replace_text(self, selector: str, value: str) -> None:
            self.operations.append(("replace_text", selector, value))
            self.values[selector] = "(555) 010-9999"

    page = FormattedTelephonePage()

    evidence = browser_actions.replace_tel_local_digits(page, "#phone", "5550109999")

    assert page.operations == [("replace_text", "#phone", "5550109999")]
    assert evidence == {
        "action": "replace_tel_local_digits",
        "selector": "#phone",
        "expected_digits": "5550109999",
        "actual_digits": "5550109999",
        "verified": True,
    }


def test_replace_tel_local_digits_rejects_a_different_local_number():
    class IncorrectTelephonePage(InMemoryPage):
        def replace_text(self, selector: str, value: str) -> None:
            self.operations.append(("replace_text", selector, value))
            self.values[selector] = "(555) 010-9998"

    evidence = browser_actions.replace_tel_local_digits(
        IncorrectTelephonePage(), "#phone", "5550109999"
    )

    assert evidence["verified"] is False


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


def test_react_select_exact_returns_selected_label_read_back_evidence():
    page = InMemoryPage()

    evidence = browser_actions.react_select_exact(
        page,
        "#school--1",
        "San Diego",
        "University of California - San Diego",
    )

    assert page.operations == [("react_select_exact", "#school--1", "San Diego")]
    assert evidence == {
        "action": "react_select_exact",
        "selector": "#school--1",
        "search_text": "San Diego",
        "expected": "University of California - San Diego",
        "actual": "University of California - San Diego",
        "verified": True,
    }


def test_react_select_can_verify_a_selected_label_distinct_from_option_text():
    class CountryPage(InMemoryPage):
        def react_select_exact(self, selector, search_text, exact_option):
            self.operations.append(("react_select_exact", selector, search_text))
            self.values[selector] = "+1"

    page = CountryPage()

    evidence = browser_actions.react_select_exact(
        page,
        "#country",
        "United States",
        "United States +1",
        selected_option="+1",
    )

    assert evidence["expected"] == "+1"
    assert evidence["actual"] == "+1"
    assert evidence["verified"] is True


def test_react_select_waits_for_framework_read_back_after_rerender():
    class DelayedReactPage(InMemoryPage):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def read_react_selected_option(self, selector):
            self.reads += 1
            return "" if self.reads == 1 else self.values[selector]

    page = DelayedReactPage()

    evidence = browser_actions.react_select_exact(
        page,
        "#school",
        "San Diego",
        "University of California - San Diego",
    )

    assert page.reads == 2
    assert evidence["verified"] is True


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


def test_cdp_upload_waits_for_rendered_filename_after_async_upload():
    class DelayedUploadPage(InMemoryPage):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def read_uploaded_filename(self, selector):
            self.reads += 1
            if self.reads < 3:
                return ""
            return self.values[selector]

    page = DelayedUploadPage()

    evidence = browser_actions.cdp_upload(
        page, "#resume-upload", "/safe/Resume.pdf"
    )

    assert page.reads == 3
    assert evidence["verified"] is True


def test_cdp_upload_preserves_an_exact_existing_application_upload():
    page = InMemoryPage()
    page.values["#resume-upload"] = "Resume.pdf"

    evidence = browser_actions.cdp_upload(
        page, "#resume-upload", "/safe/Resume.pdf"
    )

    assert page.operations == []
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
