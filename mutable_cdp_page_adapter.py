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
            "Runtime.evaluate", {
                "expression": expression,
                "returnByValue": return_by_value,
                "awaitPromise": True,
            }
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

    def _scroll_selector_into_view(self, selector: str) -> bool:
        document = self._connection.call("DOM.getDocument", {"depth": 1})
        root = document.get("root", {})
        root_id = root.get("nodeId") if isinstance(root, dict) else None
        if not isinstance(root_id, int):
            return False
        matches = self._connection.call(
            "DOM.querySelectorAll", {"nodeId": root_id, "selector": selector}
        ).get("nodeIds", [])
        if not isinstance(matches, list) or len(matches) != 1:
            return False
        try:
            self._connection.call("DOM.scrollIntoViewIfNeeded", {"nodeId": matches[0]})
        except RuntimeError:
            # Hidden file inputs deliberately have no box model but remain valid
            # CDP upload targets; the following typed-control check handles them.
            pass
        return True

    @staticmethod
    def _script(selector: str, body: str, *values: object) -> str:
        selector_json = json.dumps(selector)
        encoded_values = tuple(json.dumps(value) for value in values)
        return (
            "(() => { const element = document.querySelector(" + selector_json + "); "
            "if (document.querySelectorAll(" + selector_json + ").length !== 1) "
            "throw new Error('exactly one control required'); "
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
        self._scroll_selector_into_view(selector)
        try:
            self._evaluate(self._script(selector, body, *values))
        except RuntimeError as exc:
            raise PageControlError(str(exc)) from exc

    def read_only_snapshot(self) -> dict[str, object]:
        self._fresh_target()
        return {"target_id": self.target_id, "url": self.target_url, "read_only": True}

    def inspect_safety_surface(self, selectors: list[str]) -> dict[str, object]:
        """Observe exact-page control/overlay facts for the browser canary."""
        if not selectors or not all(isinstance(selector, str) and selector for selector in selectors):
            raise PageControlError("learned canary selectors are required")
        self._fresh_target()
        states = []
        for selector in selectors:
            self._scroll_selector_into_view(selector)
            value = self._evaluate(
                "(() => { const matches = [...document.querySelectorAll(" + json.dumps(selector) + ")]; "
                "const element = matches[0]; if (!element) return {count: matches.length, visible: false, enabled: false, unobscured: false, retina_scale: window.devicePixelRatio}; "
                "const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); "
                "const fileInput = element.tagName === 'INPUT' && element.type === 'file'; "
                "const visible = fileInput || (style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0); "
                "const top = !fileInput && visible ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null; "
                "return {count: matches.length, visible, enabled: !element.disabled, unobscured: fileInput || top === element || element.contains(top), retina_scale: window.devicePixelRatio}; })()"
            )
            if not isinstance(value, dict):
                raise PageControlError("exact-page safety surface was unavailable")
            states.append(value)
        return {
            "retina_scale": states[0].get("retina_scale", 1),
            "control_visible": all(
                item.get("count") == 1
                and item.get("visible") is True
                and item.get("enabled") is True
                and item.get("unobscured") is True
                for item in states
            ),
            "overlay_present": any(
                item.get("visible") is True
                and item.get("enabled") is True
                and item.get("unobscured") is not True
                for item in states
            ),
            "native_window_detected": False,
        }

    def replace_text(self, selector: str, value: str) -> None:
        self._mutate(
            selector,
            "if (!['INPUT', 'TEXTAREA'].includes(element.tagName)) "
            "throw new Error('text input required'); "
            "const prototype = element.tagName === 'TEXTAREA' "
            "? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; "
            "const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set; "
            "element.focus(); setter.call(element, {0}); "
            "element.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: {0}}})); "
            "element.dispatchEvent(new Event('change', {{bubbles: true}})); element.blur(); "
            "return {{visible, enabled}};",
            value,
        )

    def read_value(self, selector: str) -> str:
        self._fresh_target()
        self._scroll_selector_into_view(selector)
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

    def react_select_exact(self, selector: str, search_text: str, exact_option: str) -> None:
        """Clear, filter, and select one exact React option without an awaited DOM promise."""
        import time

        self._fresh_target()
        self._scroll_selector_into_view(selector)
        activate = (
            "const activate = node => { for (const type of ['mousedown', 'mouseup', 'click']) "
            "node.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, button: 0, buttons: type === 'mousedown' ? 1 : 0})); }; "
        )
        initialize = (
            "(() => { const selector = " + json.dumps(selector) + "; "
            "const searchText = " + json.dumps(search_text) + "; "
            + activate
            + "const element = document.querySelector(selector); "
            "if (!element) throw new Error('control not found'); "
            "const style = getComputedStyle(element); "
            "if (style.display === 'none' || style.visibility === 'hidden' || !element.getClientRects().length || element.disabled) "
            "throw new Error('control must be visible and enabled'); "
            "const control = element.closest('.select__control'); "
            "if (!control) throw new Error('React Select control required'); "
            "const clear = control.querySelector('button[aria-label=\"Clear selections\"]'); "
            "if (clear) activate(clear); "
            "const liveElement = document.querySelector(selector); "
            "if (!liveElement) throw new Error('control disappeared after clear'); "
            "const liveControl = liveElement.closest('.select__control'); "
            "if (!liveControl) throw new Error('React Select control disappeared after clear'); "
            "if (liveElement.getAttribute('aria-expanded') !== 'true') activate(liveControl); "
            "const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; "
            "liveElement.focus(); setter.call(liveElement, searchText); "
            "liveElement.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: searchText})); "
            "liveElement.dispatchEvent(new Event('change', {bubbles: true})); "
            "const toggle = liveControl.querySelector('button[aria-label=\"Toggle flyout\"]'); "
            "if (liveElement.getAttribute('aria-expanded') !== 'true' && toggle) activate(toggle); "
            "return true; })()"
        )
        self._evaluate(initialize)

        deadline = time.monotonic() + 2.5
        labels: list[str] = []
        while time.monotonic() < deadline:
            result = self._evaluate(
                "(() => { const exactOption = " + json.dumps(exact_option) + "; "
                + activate
                + "const options = [...document.querySelectorAll('[role=\"option\"]')].filter(option => option.getClientRects().length > 0); "
                "const labels = options.map(option => option.innerText.trim()); "
                "const match = options.find(option => option.innerText.trim() === exactOption); "
                "if (match) { activate(match); return {selected: true, labels}; } "
                "return {selected: false, labels}; })()"
            )
            if isinstance(result, dict):
                observed = result.get("labels")
                if isinstance(observed, list):
                    labels = [str(item) for item in observed]
                if result.get("selected") is True:
                    return
            time.sleep(0.05)
        raise PageControlError(
            "exact React Select option not found: " + " | ".join(labels)
        )

    def read_react_selected_option(self, selector: str) -> str:
        self._fresh_target()
        value = self._evaluate(
            "(() => { const element = document.querySelector(" + json.dumps(selector) + "); "
            "if (!element) throw new Error('control not found'); "
            "const control = element.closest('.select__control'); "
            "if (!control) throw new Error('React Select control required'); "
            "const selected = control.querySelector('.select__single-value'); "
            "return selected ? selected.innerText.trim() : ''; })()"
        )
        return value if isinstance(value, str) else ""

    def set_checked(self, selector: str, checked: bool) -> None:
        self._mutate(
            selector,
            "if (!['checkbox', 'radio'].includes(element.type)) throw new Error('checkable control required'); "
            "if (Boolean(element.checked) !== {0}) element.click(); "
            "return {{visible, enabled}};",
            checked,
        )

    def read_checked(self, selector: str) -> bool:
        self._fresh_target()
        self._scroll_selector_into_view(selector)
        return self._evaluate(self._script(selector, "return Boolean(element.checked);")) is True

    def cdp_upload(self, selector: str, path: str) -> None:
        self._fresh_target()
        result = self._evaluate(
            "(() => { const matches = [...document.querySelectorAll(" + json.dumps(selector) + ")]; "
            "if (matches.length !== 1) throw new Error('exactly one file input required'); "
            "const element = matches[0]; if (element.tagName !== 'INPUT' || element.type !== 'file') "
            "throw new Error('file input required'); if (element.disabled) "
            "throw new Error('file input must be enabled'); return element; })()",
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
            "(() => { const element = document.querySelector(" + json.dumps(selector) + "); "
            "if (element && element.files && element.files[0]) return element.files[0].name; "
            "const text = document.querySelector('#application-form')?.innerText || document.body?.innerText || ''; "
            "const match = text.match(/(?:^|\\n)([^\\n]+\\.pdf)(?:$|\\n)/i); "
            "return match ? match[1].trim() : ''; })()",
        )
        return value if isinstance(value, str) else ""

    def read_uploaded_sha256(self, selector: str) -> str:
        """Read an ATS-exposed upload digest when present; absence is explicit."""
        self._fresh_target()
        value = self._evaluate(
            "(() => { const element = document.querySelector(" + json.dumps(selector) + "); "
            "if (!element) return ''; "
            "return element.dataset.uploadedSha256 || element.dataset.fileSha256 || ''; })()"
        )
        return value if isinstance(value, str) else ""

    def inspect_submit_control(self, selector: str) -> dict[str, object]:
        """Observe one exact submit control without activating it."""
        self._fresh_target()
        self._scroll_selector_into_view(selector)
        value = self._evaluate(
            "(() => { const selector = " + json.dumps(selector) + "; "
            "const matches = [...document.querySelectorAll(selector)]; const element = matches[0]; "
            "if (!element) return {count: 0}; const style = getComputedStyle(element); "
            "const rect = element.getBoundingClientRect(); "
            "const visible = style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0; "
            "const top = visible ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null; "
            "return {count: matches.length, visible, enabled: !element.disabled, "
            "unobscured: top === element || element.contains(top), "
            "role: element.getAttribute('role') || (element.tagName === 'BUTTON' ? 'button' : '')}; })()"
        )
        state = value if isinstance(value, dict) else {}
        return {
            "selector": selector,
            "target_id": self.target_id,
            "url": self.target_url,
            "visible": state.get("visible") is True and state.get("unobscured") is True,
            "enabled": state.get("enabled") is True,
            "unique": state.get("count") == 1,
            "role": state.get("role"),
        }

    def click_submit_once(self, selector: str) -> None:
        """Activate one verified DOM submit control; authorization lives upstream."""
        self._fresh_target()
        self._scroll_selector_into_view(selector)
        self._evaluate(
            "(() => { const selector = " + json.dumps(selector) + "; "
            "const matches = [...document.querySelectorAll(selector)]; const element = matches[0]; "
            "if (matches.length !== 1 || !element) throw new Error('unique submit control required'); "
            "const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); "
            "const visible = style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0; "
            "const top = visible ? document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) : null; "
            "const role = element.getAttribute('role') || (element.tagName === 'BUTTON' ? 'button' : ''); "
            "if (!visible || element.disabled || !(top === element || element.contains(top)) || role !== 'button') "
            "throw new Error('submit control must be visible, enabled, unobscured, and button-role'); "
            "element.click(); return true; })()"
        )

    def inspect_confirmation(self) -> dict[str, object]:
        """Conservatively observe a page-declared submitted state without replay."""
        self._fresh_target()
        value = self._evaluate(
            "(() => { const declared = document.body && document.body.dataset.submitted === 'true'; "
            "const marker = document.querySelector('[data-submission-state=" + '"submitted"' + "]'); "
            "const visible = marker && getComputedStyle(marker).display !== 'none' && getComputedStyle(marker).visibility !== 'hidden'; "
            "return {confirmed: Boolean(declared || visible), state: (declared || visible) ? 'submitted' : 'unknown'}; })()"
        )
        return value if isinstance(value, dict) else {"confirmed": False, "state": "unknown"}


class WorkerPreparationAdapter(MutableCDPPageAdapter):
    """By-value field preparation; never scrolls or takes native input focus.

    Construct only through an explicitly opted-in approved WorkerTransport.
    Session-scoped CDP handles are not supported by that worker.
    """

    def __init__(self, *, target_id: str, target_url: str, connection: CDPConnection,
                 preparation_step: str = "application", approved_upload_path: str | None = None) -> None:
        from tenant_field_maps import resolve_field_map, FieldMapError

        super().__init__(target_id=target_id, target_url=target_url, connection=connection)
        mappings = []
        for platform in ("greenhouse", "workday", "njoyn"):
            try:
                mappings.append(resolve_field_map(page_url=target_url, platform=platform))
            except FieldMapError:
                continue
        if len(mappings) != 1 or preparation_step not in mappings[0]["steps"]:
            raise PageControlError("exact learned preparation tenant and step required")
        self._controls = mappings[0]["steps"][preparation_step]["controls"]
        self._approved_upload_path = approved_upload_path

    def _require_operation(self, selector: str, operation: str) -> None:
        import re
        if any(item["selector"] == selector and re.search(
                r"consent|privacy|password|security|credential|acknowledg|terms|certif", field, re.I)
               for field, item in self._controls.items()):
            raise PageControlError("active consent/security semantic fields are prohibited")
        matches = [item for item in self._controls.values() if item["selector"] == selector]
        permitted = {operation}
        if operation == "replace_text":
            permitted.add("replace_tel_local_digits")
        if len(matches) != 1 or matches[0]["operation"] not in permitted:
            raise PageControlError("selector/operation outside exact learned preparation step")

    def _scroll_selector_into_view(self, selector: str) -> bool:
        return False

    @staticmethod
    def _control_guard() -> str:
        return (
            "if ([...document.querySelectorAll('[role=\"dialog\"],[aria-modal=\"true\"],input[type=\"password\"]')].some(n => "
            "n.getClientRects().length && getComputedStyle(n).display !== 'none' && getComputedStyle(n).visibility !== 'hidden')) "
            "throw new Error('active dialog or sign-in gate prohibits preparation'); "
            "const education = [...document.querySelectorAll('input[id],select[id]')].map(n => "
            "n.id.match(/^(?:school|degree|discipline|start-month|start-year|end-month|end-year)--(\\d+)$/)).filter(Boolean); "
            "if (new Set(education.map(m => m[1])).size > 1) throw new Error('repeated education blocks prohibited'); "
            "const label = [element.id, element.name, element.getAttribute('aria-label'), "
            "element.getAttribute('autocomplete'), ...[...(element.labels || [])].map(n => n.textContent)].join(' '); "
            "if (/password|passcode|one-time-code|captcha|consent|privacy|agree|terms|credential|security/i.test(label) "
            "|| element.type === 'password') throw new Error('protected control prohibited'); "
            "if (element.readOnly || element.getAttribute('aria-disabled') === 'true') "
            "throw new Error('control must be editable'); "
        )
    @staticmethod
    def _script(selector: str, body: str, *values: object) -> str:
        return MutableCDPPageAdapter._script(selector, WorkerPreparationAdapter._control_guard() + body, *values)

    def replace_text(self, selector: str, value: str) -> None:
        self._require_operation(selector, "replace_text")
        self._mutate(
            selector,
            "if (!(element.tagName === 'TEXTAREA' || (element.tagName === 'INPUT' "
            "&& ['text','email','tel','url','search','number'].includes(element.type))) "
            "|| element.getAttribute('role') === 'combobox' || element.hasAttribute('list')) "
            "throw new Error('text input required'); "
            "const prototype = element.tagName === 'TEXTAREA' "
            "? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; "
            "const setter = Object.getOwnPropertyDescriptor(prototype, 'value').set; "
            "setter.call(element, {0}); "
            "element.dispatchEvent(new InputEvent('input', {{bubbles: true, inputType: 'insertText', data: {0}}})); "
            "element.dispatchEvent(new Event('change', {{bubbles: true}})); "
            "return {{visible, enabled}};", value,
        )

    def select_option(self, selector: str, value: str) -> None:
        self._require_operation(selector, "native_select")
        self._mutate(
            selector,
            "if (element.tagName !== 'SELECT' || element.multiple) throw new Error('single native select required'); "
            "const options = [...element.options].filter(o => o.value === {0}); "
            "if (options.length !== 1 || options[0].disabled) throw new Error('one enabled exact native option required'); "
            "Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(element, {0}); "
            "element.dispatchEvent(new Event('input', {{bubbles:true}})); "
            "element.dispatchEvent(new Event('change', {{bubbles:true}})); return true;", value,
        )

    def read_selected_option(self, selector: str) -> str:
        self._require_operation(selector, "native_select")
        self._fresh_target()
        value = self._evaluate(self._script(selector,
            "if (element.tagName !== 'SELECT' || element.selectedOptions.length !== 1) "
            "throw new Error('one selected native option required'); return element.selectedOptions[0].value;"))
        return value if isinstance(value, str) else ""

    _react_control = (
        "if (element.tagName !== 'INPUT' || element.type !== 'text' || element.getAttribute('role') !== 'combobox') "
        "throw new Error('learned React combobox required'); "
        "const control = element.closest('.select__control'); "
        "if (!control || control.querySelectorAll('input[role=\"combobox\"]').length !== 1) "
        "throw new Error('one React combobox per control required'); "
    )
    _activate = (
        "const activate = node => {{ for (const type of ['mousedown','mouseup','click']) "
        "node.dispatchEvent(new MouseEvent(type, {{bubbles:true,cancelable:true,view:window,button:0}})); }}; "
    )

    def react_select_exact(self, selector: str, search_text: str, exact_option: str) -> None:
        import time

        self._require_operation(selector, "react_select_exact")
        self._mutate(selector, self._react_control + self._activate +
                     "if (element.getAttribute('aria-expanded') !== 'true') activate(control); return true;")
        # Each rerender gets a fresh unique selector; never retain a DOM handle.
        self._mutate(selector, self._react_control +
                     "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(element,{0}); "
                     "element.dispatchEvent(new InputEvent('input',{{bubbles:true,inputType:'insertText',data:{0}}})); "
                     "element.dispatchEvent(new Event('change',{{bubbles:true}})); return true;", search_text)
        deadline = time.monotonic() + 2.5
        while True:
            self._fresh_target()
            selected = self._evaluate(self._script(selector, self._react_control + self._activate +
                "const refs = (element.getAttribute('aria-controls') || element.getAttribute('aria-owns') || '').trim().split(/\\s+/).filter(Boolean); "
                "if (refs.length !== 1) throw new Error('one target-owned listbox required'); "
                "const lists = [...document.querySelectorAll('[id=' + JSON.stringify(refs[0]) + ']')]; "
                "if (!lists.length) return false; "
                "if (lists.length !== 1 || lists[0].getAttribute('role') !== 'listbox') throw new Error('ambiguous owned listbox'); "
                "const options = [...lists[0].querySelectorAll('[role=\"option\"]')].filter(o => o.innerText.trim() === {0}); "
                "if (!options.length) return false; "
                "if (options.length !== 1) throw new Error('ambiguous exact option'); "
                "const option = options[0], optionStyle = getComputedStyle(option), optionRect = option.getBoundingClientRect(); "
                "const top = document.elementFromPoint(optionRect.left+optionRect.width/2,optionRect.top+optionRect.height/2); "
                "if (!option.getClientRects().length || optionStyle.display === 'none' || optionStyle.visibility === 'hidden' "
                "|| option.disabled || option.getAttribute('aria-disabled') === 'true' || !(top === option || option.contains(top))) "
                "throw new Error('exact option must be visible enabled and unobscured'); "
                "activate(option); return true;", exact_option))
            if selected is True:
                return
            if time.monotonic() >= deadline:
                raise PageControlError("exact option unavailable in target-owned listbox")
            time.sleep(0.05)  # Observation retry only; never repeat an activation.

    def read_react_selected_option(self, selector: str) -> str:
        self._require_operation(selector, "react_select_exact")
        self._fresh_target()
        value = self._evaluate(self._script(selector, self._react_control +
            "const selected = [...control.querySelectorAll('.select__single-value')]; "
            "if (selected.length !== 1 || element.value !== '' || element.getAttribute('aria-expanded') === 'true') return ''; "
            "return selected[0].innerText.trim();"))
        return value if isinstance(value, str) else ""

    @staticmethod
    def _file_script(selector: str, body: str, *values: object) -> str:
        return (
            "(() => { const matches = [...document.querySelectorAll(" + json.dumps(selector) + ")]; "
            "if (matches.length !== 1) throw new Error('one exact file input required'); const element = matches[0]; "
            "if (element.tagName !== 'INPUT' || element.type !== 'file' || element.disabled) throw new Error('enabled file input required'); "
            + WorkerPreparationAdapter._control_guard()
            + body.format(*(json.dumps(value) for value in values)) + " })()"
        )

    def cdp_upload(self, selector: str, path: str) -> None:
        """Native File assignment using bounded by-value chunks, never CDP handles.

        This proves browser File bytes only, not ATS upload acceptance or Review.
        No activation is retried; any uncertain response stops preparation.
        """
        import base64
        import hashlib
        from pathlib import Path
        import uuid

        self._require_operation(selector, "cdp_upload")
        source = Path(path)
        content = self._approved_file_bytes(path)
        digest = hashlib.sha256(content).hexdigest()
        key = "__worker_upload_" + uuid.uuid4().hex
        self._fresh_target()
        supported = self._evaluate(self._file_script(selector,
            "if (typeof File !== 'function' || typeof DataTransfer !== 'function' || typeof crypto === 'undefined' || !crypto.subtle "
            "|| !Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'files')?.set) return false; "
            "Object.defineProperty(window,{0},{{configurable:true,value:{{element,chunks:[],size:0}}}}); return true;", key))
        if supported is not True:
            raise PageControlError("native File/DataTransfer/digest upload unsupported; no handle fallback")
        try:
            for offset in range(0, len(content), 24000):
                encoded = base64.b64encode(content[offset:offset + 24000]).decode('ascii')
                self._evaluate(self._file_script(selector,
                    "const state=window[{0}]; if (!state || state.element !== element || state.size !== {1}) "
                    "throw new Error('upload state drift'); const bytes=Uint8Array.from(atob({2}), c=>c.charCodeAt(0)); "
                    "state.chunks.push(bytes); state.size += bytes.length; return state.size;", key, offset, encoded))
            receipt = self._evaluate(self._file_script(selector,
                "return (async () => {{ const state=window[{0}]; "
                "if (!state || state.element !== element || state.size !== {1}) throw new Error('upload state drift'); "
                "const bytes=new Uint8Array(state.size); let offset=0; for(const chunk of state.chunks) {{bytes.set(chunk,offset);offset+=chunk.length;}} "
                "const hex = async data => [...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(v=>v.toString(16).padStart(2,'0')).join(''); "
                "if (await hex(bytes) !== {2}) throw new Error('upload bytes digest mismatch'); "
                "if (location.href !== {3} || document.querySelectorAll({4}).length !== 1 || document.querySelector({4}) !== element) throw new Error('upload target drift'); "
                + self._control_guard() +
                "const file=new File([bytes],{5},{{type:'application/pdf'}}), transfer=new DataTransfer(); transfer.items.add(file); "
                "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'files').set.call(element,transfer.files); "
                "const attached=element.files; if (attached.length !== 1) throw new Error('one attached File required'); "
                "const actual={{name:attached[0].name,size:attached[0].size,sha256:await hex(await attached[0].arrayBuffer())}}; "
                "if (actual.name !== {5} || actual.size !== {1} || actual.sha256 !== {2}) throw new Error('attached File digest mismatch'); "
                "{{ if (location.href !== {3} || document.querySelectorAll({4}).length !== 1 || document.querySelector({4}) !== element "
                "|| element.disabled || element.type !== 'file') throw new Error('upload target drift'); "
                + self._control_guard() + "}} "
                "element.dispatchEvent(new Event('input',{{bubbles:true}})); element.dispatchEvent(new Event('change',{{bubbles:true}})); "
                "delete window[{0}]; return actual; }})();", key, len(content), digest, self.target_url, selector, source.name))
            if receipt != {"name": source.name, "size": len(content), "sha256": digest}:
                raise PageControlError("uploaded File read-back unavailable; do not replay")
        finally:
            # Cleanup is not a retry of File assignment. URL drift fails closed;
            # navigation destroys the old realm instead of touching the new page.
            try:
                self._evaluate("(() => { delete window[" + json.dumps(key) + "]; return true; })()")
            except (OSError, ValueError, RuntimeError):
                pass

    def read_uploaded_filename(self, selector: str) -> str:
        self._require_operation(selector, "cdp_upload")
        self._fresh_target()
        value = self._evaluate(self._file_script(selector,
            "return element.files.length === 1 ? element.files[0].name : '';"))
        return value if isinstance(value, str) else ""

    def read_uploaded_sha256(self, selector: str) -> str:
        self._require_operation(selector, "cdp_upload")
        self._fresh_target()
        value = self._evaluate(self._file_script(selector,
            "if (element.files.length !== 1) return ''; return (async () => {{ "
            "const bytes=await element.files[0].arrayBuffer(); "
            "return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join(''); }})();"))
        return value if isinstance(value, str) else ""

    def _approved_file_bytes(self, path: str) -> bytes:
        from pathlib import Path

        source = Path(path)
        if path != self._approved_upload_path or not source.is_absolute() or source.is_symlink():
            raise PageControlError("exact explicitly approved resume path required")
        if not source.is_file() or not 0 < source.stat().st_size <= 10 * 1024 * 1024:
            raise PageControlError("resume must be a nonempty regular file no larger than 10 MiB")
        content = source.read_bytes()
        if source.suffix.lower() != '.pdf' or not content.startswith(b'%PDF-'):
            raise PageControlError("only the approved PDF resume is supported")
        return content

    def uploaded_file_matches(self, selector: str, path: str) -> bool:
        import hashlib
        self._require_operation(selector, "cdp_upload")
        digest = hashlib.sha256(self._approved_file_bytes(path)).hexdigest()
        return self.read_uploaded_sha256(selector) == digest
