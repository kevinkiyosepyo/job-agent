"""Deterministic, verification-first browser action contracts."""
from __future__ import annotations

from pathlib import Path
from html.parser import HTMLParser
from typing import Protocol


class _FormInventoryParser(HTMLParser):
    """Small text-only tree; void elements never steal sibling labels."""

    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[dict] = []
        self.stack: list[int] = []

    def handle_starttag(self, tag, attrs):
        index = len(self.nodes)
        self.nodes.append({"tag": tag, "attrs": dict(attrs), "text": [],
                           "parent": self.stack[-1] if self.stack else None,
                           "ancestors": list(self.stack)})
        if tag not in {"input", "br", "hr", "img", "meta", "link", "source", "wbr", "area", "base", "embed", "param", "col", "track"}:
            self.stack.append(index)

    def handle_endtag(self, tag):
        for pos in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[pos]]["tag"] == tag:
                del self.stack[pos:]
                return

    def handle_data(self, data):
        if any(self.nodes[i]["tag"] in {"script", "style", "noscript"} for i in self.stack):
            return
        in_value = any(self.nodes[i]["tag"] in {"select", "textarea"} for i in self.stack)
        for i in self.stack:
            if self.nodes[i]["tag"] != "label" or not in_value:
                self.nodes[i]["text"].append(data)


def inventory_form_fields(html_text: str) -> list[dict]:
    """Fresh required-question inventory, not values or saved Review evidence.

    Includes orphan controls and ARIA comboboxes. Labels are resolved only from
    explicit ID relations, wrapping labels, or one unambiguous sibling label.
    """
    parser = _FormInventoryParser()
    parser.feed(html_text)
    nodes = parser.nodes
    controls = [i for i, n in enumerate(nodes) if n["tag"] in {"input", "select", "textarea"}
                or n["attrs"].get("role") == "combobox"]
    labels = [i for i, n in enumerate(nodes) if n["tag"] == "label"]

    def text(index):
        return " ".join(" ".join(nodes[index]["text"]).replace("*", " ").split())

    fields = []
    for index in controls:
        node = nodes[index]
        attrs = node["attrs"]
        refs = (attrs.get("aria-labelledby") or "").split()
        referenced = [[i for i, n in enumerate(nodes) if n["attrs"].get("id") == ref] for ref in refs]
        label = ""
        if referenced and all(len(matches) == 1 for matches in referenced):
            label = " ".join(text(matches[0]) for matches in referenced)
        elif attrs.get("aria-label"):
            label = str(attrs["aria-label"]).strip()
        else:
            linked = [i for i in labels if attrs.get("id") and nodes[i]["attrs"].get("for") == attrs["id"]]
            wrapped = [i for i in node["ancestors"] if i in labels]
            siblings = [i for i in labels if nodes[i]["parent"] == node["parent"] and not nodes[i]["attrs"].get("for")]
            sibling_controls = [i for i in controls if nodes[i]["parent"] == node["parent"]]
            candidates = linked or wrapped or (siblings if len(sibling_controls) == 1 else [])
            if len(candidates) == 1:
                label = text(candidates[0])
        fields.append({
            "label": label, "name": attrs.get("name") or attrs.get("id") or "",
            "type": "combobox" if attrs.get("role") == "combobox" else attrs.get("type") or ("text" if node["tag"] == "input" else node["tag"]),
            "required": "required" in attrs or str(attrs.get("aria-required", "")).lower() == "true",
        })
    return fields


class TextPage(Protocol):
    def replace_text(self, selector: str, value: str) -> None: ...

    def read_value(self, selector: str) -> str: ...


class NativeSelectPage(Protocol):
    def select_option(self, selector: str, value: str) -> None: ...

    def read_selected_option(self, selector: str) -> str: ...


class ReactSelectPage(Protocol):
    def react_select_exact(self, selector: str, search_text: str, exact_option: str) -> None: ...

    def read_react_selected_option(self, selector: str) -> str: ...


class CheckedPage(Protocol):
    def set_checked(self, selector: str, checked: bool) -> None: ...

    def read_checked(self, selector: str) -> bool: ...


class CDPUploadPage(Protocol):
    def cdp_upload(self, selector: str, path: str) -> None: ...

    def read_uploaded_filename(self, selector: str) -> str: ...


class ScrollClickPage(Protocol):
    def scroll_into_view(self, selector: str) -> None: ...

    def click(self, selector: str) -> None: ...

    def read_post_click_state(self, selector: str) -> str: ...


class SubmitConfirmPage(Protocol):
    def submit(self, selector: str) -> None: ...

    def read_confirmation(self) -> str: ...


def replace_text(page: TextPage, selector: str, value: str) -> dict[str, object]:
    """Replace a field's text and return evidence from an exact read-back."""
    page.replace_text(selector, value)
    actual = page.read_value(selector)
    return {
        "action": "replace_text",
        "selector": selector,
        "expected": value,
        "actual": actual,
        "verified": actual == value,
    }


def replace_tel_local_digits(page: TextPage, selector: str, value: str) -> dict[str, object]:
    """Replace a telephone field while accepting only presentation-format changes.

    Greenhouse's international-telephone widget reformats a truthful local number
    after blur. The country is selected separately, so verification preserves the
    local digits and does not accept a country-code change.
    """
    expected_digits = "".join(character for character in value if character.isdigit())
    if not expected_digits:
        raise ValueError("telephone answer must contain local digits")
    page.replace_text(selector, value)
    actual = page.read_value(selector)
    actual_digits = "".join(character for character in actual if character.isdigit())
    return {
        "action": "replace_tel_local_digits",
        "selector": selector,
        "expected_digits": expected_digits,
        "actual_digits": actual_digits,
        "verified": actual_digits == expected_digits,
    }


def native_select(page: NativeSelectPage, selector: str, value: str) -> dict[str, object]:
    """Select a native option and return evidence from selected-option read-back."""
    page.select_option(selector, value)
    actual = page.read_selected_option(selector)
    return {
        "action": "native_select",
        "selector": selector,
        "expected": value,
        "actual": actual,
        "verified": actual == value,
    }


def react_select_exact(
    page: ReactSelectPage,
    selector: str,
    search_text: str,
    exact_option: str,
    *,
    selected_option: str | None = None,
) -> dict[str, object]:
    """Select one exact React Select option and verify its rendered label."""
    page.react_select_exact(selector, search_text, exact_option)
    expected = selected_option if selected_option is not None else exact_option
    actual = page.read_react_selected_option(selector)
    if actual != expected:
        import time

        deadline = time.monotonic() + 1.0
        while actual != expected and time.monotonic() < deadline:
            time.sleep(0.05)
            actual = page.read_react_selected_option(selector)
    return {
        "action": "react_select_exact",
        "selector": selector,
        "search_text": search_text,
        "expected": expected,
        "actual": actual,
        "verified": actual == expected,
    }


def set_checked(page: CheckedPage, selector: str, checked: bool) -> dict[str, object]:
    """Set a radio or checkbox state and return checked-state read-back evidence."""
    page.set_checked(selector, checked)
    actual = page.read_checked(selector)
    return {
        "action": "set_checked",
        "selector": selector,
        "expected": checked,
        "actual": actual,
        "verified": actual == checked,
    }


def cdp_upload(page: CDPUploadPage, selector: str, path: str) -> dict[str, object]:
    """Attach the exact file unless its verified application slot already has it."""
    expected = Path(path).name
    actual = page.read_uploaded_filename(selector)
    digest_required = getattr(page, "requires_upload_digest", False) is True
    matches = getattr(page, "uploaded_file_matches", None)
    if digest_required and not callable(matches):
        raise ValueError("byte-verified upload requires an exact File digest reader")
    byte_verified = bool(matches(selector, path)) if digest_required else True
    if actual != expected or not byte_verified:
        page.cdp_upload(selector, path)
        actual = page.read_uploaded_filename(selector)
        if actual != expected:
            import time

            deadline = time.monotonic() + 2.0
            while actual != expected and time.monotonic() < deadline:
                time.sleep(0.05)
                actual = page.read_uploaded_filename(selector)
        byte_verified = bool(matches(selector, path)) if digest_required else True
    return {
        "action": "cdp_upload",
        "selector": selector,
        "expected": expected,
        "actual": actual,
        "verified": actual == expected and byte_verified,
        **({"byte_verified": byte_verified, "verification_scope": "browser_file_bytes"} if digest_required else {}),
    }


def scroll_and_click(
    page: ScrollClickPage, selector: str, expected_state: str
) -> dict[str, object]:
    """Scroll to a control, click it, and return post-click read-back evidence."""
    page.scroll_into_view(selector)
    page.click(selector)
    actual = page.read_post_click_state(selector)
    return {
        "action": "scroll_and_click",
        "selector": selector,
        "expected": expected_state,
        "actual": actual,
        "verified": actual == expected_state,
    }


def submit_and_confirm(
    page: SubmitConfirmPage, selector: str, expected_confirmation: str
) -> dict[str, object]:
    """Submit once and return evidence from explicit confirmation read-back."""
    page.submit(selector)
    actual = page.read_confirmation()
    return {
        "action": "submit_and_confirm",
        "selector": selector,
        "expected": expected_confirmation,
        "actual": actual,
        "verified": actual == expected_confirmation,
    }
