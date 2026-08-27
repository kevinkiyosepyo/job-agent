from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.value = "Old value"
        self.filename = "Resume.pdf"

    def call(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if method == "DOM.requestNode":
            return {"nodeId": 17}
        if method == "DOM.setFileInputFiles":
            return {}
        if params.get("returnByValue") is False:
            return {"result": {"objectId": "file-input-object"}}
        expression = params["expression"]
        if expression == "location.href":
            return {"result": {"value": "https://careers.example.test/apply"}}
        if "element.files && element.files[0]" in expression:
            return {"result": {"value": self.filename}}
        if "return Boolean(element.checked)" in expression:
            return {"result": {"value": True}}
        if expression.startswith("(() => { const element = document.querySelector") and "return element.value" in expression:
            return {"result": {"value": self.value}}
        if expression.startswith("(() => { const element = document.querySelector"):
            self.value = "Kevin"
            return {"result": {"value": {"visible": True, "enabled": True}}}
        raise AssertionError(expression)


def test_adapter_replaces_only_a_visible_enabled_exact_target_control():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.replace_text("#first-name", "Kevin")

    assert page.read_value("#first-name") == "Kevin"
    # One fresh location read occurs before both mutation and read-back.


def test_adapter_selects_real_native_option_and_reads_it_back():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.select_option("#source", "social-media")

    assert page.read_selected_option("#source") == "Kevin"


def test_adapter_sets_checked_control_and_reads_bound_state():
    import mutable_cdp_page_adapter

    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=FakeConnection(),
    )

    page.set_checked("#authorized", True)

    assert page.read_checked("#authorized") is True


def test_adapter_uploads_through_cdp_and_reads_attached_filename():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.cdp_upload("#resume", "/fixtures/Resume.pdf")

    assert page.read_uploaded_filename("#resume") == "Resume.pdf"
    assert [method for method, _ in connection.calls] == [
        "Runtime.evaluate", "Runtime.evaluate", "DOM.requestNode", "DOM.setFileInputFiles",
        "Runtime.evaluate", "Runtime.evaluate",
    ]
