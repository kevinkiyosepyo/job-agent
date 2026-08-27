"""Exact-target mutable CDP page adapter for local, approved ATS preparation.

This adapter intentionally exposes only field-level DOM operations.  It does not
navigate, synthesize desktop input, use coordinates, or access browser targets
other than the ID and URL supplied at construction.  Every operation freshly
reads ``location.href`` and rejects hidden or disabled controls before mutation.
"""
from __future__ import annotations

import json
from typing import Protocol


class CDPConnection(Protocol):
    def call(self, method: str, params: dict) -> dict: ...


class PageControlError(ValueError):
    """A requested page control is absent, hidden, disabled, or wrong-typed."""


class StaleTargetError(ValueError):
    """The bound page URL changed after its exact target was selected."""


class MutableCDPPageAdapter:
    """Bounded CDP implementation of the executor field-operation protocol."""

    def __init__(self, *, target_id: str, target_url: str, connection: CDPConnection) -> None:
        self.target_id = target_id
        self.target_url = target_url
        self._connection = connection

    def _evaluate(self, expression: str, *, return_by_value: bool = True) -> object:
        response = self._connection.call(
            "Runtime.evaluate", {"expression": expression, "returnByValue": return_by_value}
        )
        exception = response.get("exceptionDetails")
        if isinstance(exception, dict):
            detail = exception.get("text") or "CDP page evaluation failed"
            exception_value = exception.get("exception")
            if isinstance(exception_value, dict) and isinstance(exception_value.get("description"), str):
                detail = exception_value["description"]
            raise PageControlError(str(detail))
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise PageControlError("CDP returned no evaluation result")
        return result.get("value") if return_by_value else result

    def _fresh_target(self) -> None:
        if self._evaluate("location.href") != self.target_url:
            raise StaleTargetError("target URL changed before page operation")

    @staticmethod
    def _script(selector: str, body: str, *values: object) -> str:
        selector_json = json.dumps(selector)
        encoded_values = tuple(json.dumps(value) for value in values)
        return (
            "(() => { const element = document.querySelector(" + selector_json + "); "
            "if (!element) throw new Error('control not found'); "
            "const style = getComputedStyle(element); "
            "const visible = style.display !== 'none' && style.visibility !== 'hidden' "
            "&& element.getClientRects().length > 0; "
            "const enabled = !element.disabled; "
            "const rect = element.getBoundingClientRect(); "
            "const topElement = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2); "
            "const unobscured = topElement === element || element.contains(topElement); "
            "if (!visible || !enabled || !unobscured) "
            "throw new Error('control must be visible, enabled, and unobscured'); "
            + body.format(*encoded_values)
            + " })()"
        )

    def _mutate(self, selector: str, body: str, *values: object) -> None:
        self._fresh_target()
        try:
            self._evaluate(self._script(selector, body, *values))
        except RuntimeError as exc:
            raise PageControlError(str(exc)) from exc

    def read_only_snapshot(self) -> dict[str, object]:
        self._fresh_target()
        return {"target_id": self.target_id, "url": self.target_url, "read_only": True}

    def replace_text(self, selector: str, value: str) -> None:
        self._mutate(
            selector,
            "element.value = {0}; element.dispatchEvent(new Event('input', {{bubbles: true}})); "
            "element.dispatchEvent(new Event('change', {{bubbles: true}})); return {{visible, enabled}};",
            value,
        )

    def read_value(self, selector: str) -> str:
        self._fresh_target()
        value = self._evaluate(self._script(selector, "return element.value;"))
        return value if isinstance(value, str) else ""

    def select_option(self, selector: str, value: str) -> None:
        self._mutate(
            selector,
            "if (element.tagName !== 'SELECT') throw new Error('native select required'); "
            "if (![...element.options].some(option => option.value === {0})) "
            "throw new Error('native option not found'); element.value = {0}; "
            "element.dispatchEvent(new Event('input', {{bubbles: true}})); "
            "element.dispatchEvent(new Event('change', {{bubbles: true}})); return {{visible, enabled}};",
            value,
        )

    def read_selected_option(self, selector: str) -> str:
        return self.read_value(selector)

    def set_checked(self, selector: str, checked: bool) -> None:
        self._mutate(
            selector,
            "if (!['checkbox', 'radio'].includes(element.type)) throw new Error('checkable control required'); "
            "element.checked = {0}; element.dispatchEvent(new Event('input', {{bubbles: true}})); "
            "element.dispatchEvent(new Event('change', {{bubbles: true}})); return {{visible, enabled}};",
            checked,
        )

    def read_checked(self, selector: str) -> bool:
        self._fresh_target()
        return self._evaluate(self._script(selector, "return Boolean(element.checked);")) is True

    def cdp_upload(self, selector: str, path: str) -> None:
        self._fresh_target()
        result = self._evaluate(
            self._script(selector, "if (element.type !== 'file') throw new Error('file input required'); return element;"),
            return_by_value=False,
        )
        if not isinstance(result, dict) or not isinstance(result.get("objectId"), str):
            raise PageControlError("CDP did not expose a file-input object")
        node = self._connection.call("DOM.requestNode", {"objectId": result["objectId"]})
        node_id = node.get("nodeId")
        reference = (
            {"nodeId": node_id}
            if isinstance(node_id, int) and node_id > 0
            else {"objectId": result["objectId"]}
        )
        self._connection.call("DOM.setFileInputFiles", {"files": [path], **reference})

    def read_uploaded_filename(self, selector: str) -> str:
        self._fresh_target()
        value = self._evaluate(
            self._script(selector, "return element.files && element.files[0] ? element.files[0].name : '';"),
        )
        return value if isinstance(value, str) else ""
