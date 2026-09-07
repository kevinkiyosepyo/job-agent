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
        if method == "DOM.getDocument":
            return {"root": {"nodeId": 1}}
        if method == "DOM.querySelectorAll":
            return {"nodeIds": [2]}
        if method == "DOM.scrollIntoViewIfNeeded":
            return {}
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
        if "select__single-value" in expression:
            return {"result": {"value": self.value}}
        if "const exactOption =" in expression and "[role=\"option\"]" in expression:
            self.value = "University of California - San Diego"
            return {"result": {"value": {"selected": True, "labels": [self.value]}}}
        if "const searchText =" in expression and "Clear selections" in expression:
            return {"result": {"value": True}}
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


def test_read_value_scrolls_long_form_control_before_visibility_check():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.read_value("#below-fold")

    assert any(
        method == "DOM.scrollIntoViewIfNeeded"
        for method, _ in connection.calls
    )


def test_adapter_uses_native_value_setter_and_input_event_for_react_controlled_text():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.replace_text("#first-name", "Kevin")

    expression = next(
        params["expression"]
        for method, params in connection.calls
        if method == "Runtime.evaluate" and "document.querySelector" in params["expression"]
    )
    assert "Object.getOwnPropertyDescriptor" in expression
    assert "HTMLInputElement.prototype" in expression
    assert "new InputEvent('input'" in expression
    assert "element.blur()" in expression


def test_safety_surface_checks_long_form_controls_after_scrolling_each_one():
    import mutable_cdp_page_adapter

    class Connection(FakeConnection):
        def call(self, method, params):
            if method == "Runtime.evaluate" and "return {count:" in params.get("expression", ""):
                self.calls.append((method, params))
                return {"result": {"value": {
                    "count": 1,
                    "visible": True,
                    "enabled": True,
                    "unobscured": True,
                    "retina_scale": 2,
                }}}
            return super().call(method, params)

    connection = Connection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    surface = page.inspect_safety_surface(["#first-name", "#below-fold", "#resume"])

    assert surface == {
        "retina_scale": 2,
        "control_visible": True,
        "overlay_present": False,
        "native_window_detected": False,
    }
    scrolled = [
        params["nodeId"]
        for method, params in connection.calls
        if method == "DOM.scrollIntoViewIfNeeded"
    ]
    assert scrolled == [2, 2, 2]


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


def test_adapter_selects_exact_react_option_and_reads_rendered_label():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.react_select_exact(
        "#school--1",
        "San Diego",
        "University of California - San Diego",
    )

    assert page.read_react_selected_option("#school--1") == "University of California - San Diego"
    expressions = "\n".join(
        params["expression"]
        for method, params in connection.calls
        if method == "Runtime.evaluate"
    )
    assert "button[aria-label=\"Clear selections\"]" in expressions
    assert "const liveElement = document.querySelector(selector)" in expressions
    assert "button[aria-label=\"Toggle flyout\"]" in expressions
    assert "[role=\"option\"]" in expressions
    assert "new MouseEvent(type" in expressions
    assert "['mousedown', 'mouseup', 'click']" in expressions
    assert "(async" not in expressions
    assert "await new Promise" not in expressions


def test_adapter_sets_checked_control_and_reads_bound_state():
    import mutable_cdp_page_adapter

    connection = FakeConnection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    page.set_checked("#authorized", True)

    assert page.read_checked("#authorized") is True
    expression = next(
        params["expression"]
        for method, params in connection.calls
        if method == "Runtime.evaluate" and "checkable control required" in params["expression"]
    )
    assert "element.click()" in expression
    assert "element.checked =" not in expression


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
    upload_expression = next(
        params["expression"]
        for method, params in connection.calls
        if method == "Runtime.evaluate" and params.get("returnByValue") is False
    )
    assert "matches.length !== 1" in upload_expression
    assert "file input required" in upload_expression
    assert "unobscured" not in upload_expression
    assert [method for method, _ in connection.calls] == [
        "Runtime.evaluate", "Runtime.evaluate", "DOM.requestNode", "DOM.setFileInputFiles",
        "Runtime.evaluate", "Runtime.evaluate",
    ]


def test_uploaded_hash_reader_allows_ats_to_replace_file_input_after_upload():
    import mutable_cdp_page_adapter

    class Connection(FakeConnection):
        def call(self, method, params):
            if method == "Runtime.evaluate" and "uploadedSha256" in params.get("expression", ""):
                self.calls.append((method, params))
                return {"result": {"value": ""}}
            return super().call(method, params)

    connection = Connection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    assert page.read_uploaded_sha256("#resume") == ""
    expression = next(
        params["expression"]
        for method, params in connection.calls
        if method == "Runtime.evaluate" and "uploadedSha256" in params["expression"]
    )
    assert "if (!element) return ''" in expression
    assert "unobscured" not in expression


def test_submit_control_is_scrolled_into_view_before_inspection():
    import mutable_cdp_page_adapter

    class Connection(FakeConnection):
        def call(self, method, params):
            if method == "Runtime.evaluate" and "role: element.getAttribute" in params.get("expression", ""):
                self.calls.append((method, params))
                return {"result": {"value": {
                    "count": 1,
                    "visible": True,
                    "enabled": True,
                    "unobscured": True,
                    "role": "button",
                }}}
            return super().call(method, params)

    connection = Connection()
    page = mutable_cdp_page_adapter.MutableCDPPageAdapter(
        target_id="page-42",
        target_url="https://careers.example.test/apply",
        connection=connection,
    )

    state = page.inspect_submit_control("button[type='submit']")

    assert state["visible"] is True
    assert any(
        method == "DOM.scrollIntoViewIfNeeded"
        for method, _ in connection.calls
    )
