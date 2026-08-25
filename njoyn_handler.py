#!/usr/bin/env python3
"""Fixture-driven CGI/Njoyn application inspector."""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

from pipeline import validate_confirmation_evidence


class _NjoynHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.surface = ""
        self.in_h1 = False
        self.role = ""
        self.company = ""
        self.location = ""
        self.entrypoint: dict[str, str] = {}
        self.fields: list[dict[str, str]] = []
        self._apply_link_text: list[str] | None = None
        self._label_text: list[str] | None = None
        self._label_field: dict[str, str] | None = None
        self._button_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "main":
            self.surface = attr_map.get("data-surface") or self.surface
        if tag == "h1":
            self.in_h1 = True
        if tag == "label":
            self._label_text = []
            self._label_field = None
        if tag == "input":
            label = " ".join("".join(self._label_text or []).split())
            field = {
                "name": attr_map.get("name") or "",
                "type": attr_map.get("type") or "text",
                "label": label,
            }
            self.fields.append(field)
            if self._label_text is not None:
                self._label_field = field
        if tag == "button":
            self._button_text = []
        href = attr_map.get("href") or ""
        if tag == "a" and "apply" in " ".join(
            (href, attr_map.get("class") or "")
        ).casefold():
            self._apply_link_text = []
            if href:
                self.entrypoint["apply_url"] = href

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if tag == "label":
            if self._label_field is not None:
                self._label_field["label"] = " ".join(
                    "".join(self._label_text or []).split()
                )
            self._label_text = None
            self._label_field = None
        if tag == "button" and self._button_text is not None:
            label = " ".join("".join(self._button_text).split())
            if label.casefold() == "create a profile":
                self.entrypoint["create_profile_label"] = label
            self._button_text = None
        if tag == "a" and self._apply_link_text is not None:
            label = " ".join("".join(self._apply_link_text).split())
            if label:
                self.entrypoint["apply_label"] = label
            self._apply_link_text = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_h1 and not self.role:
            self.role = text
        if self._apply_link_text is not None:
            self._apply_link_text.append(text)
        if self._label_text is not None:
            self._label_text.append(text)
        if self._button_text is not None:
            self._button_text.append(text)
        if not self.company and "·" in text:
            company, _, location = text.partition("·")
            self.company = company.strip()
            self.location = location.strip()


def inspect_html(html_text: str, *, page_url: str, expected_resume_basename: str | None = None) -> dict:
    """Inventory a sanitized Njoyn surface without performing mutations."""
    parser = _NjoynHTMLParser()
    parser.feed(html_text)
    confirmation_text = None
    page_type = "application"
    try:
        confirmation_text = validate_confirmation_evidence(
            confirmation_url=page_url,
            confirmation_text=html_text,
        )
        page_type = "confirmation"
    except ValueError:
        pass
    if page_type == "application" and parser.surface == "listing" and parser.entrypoint:
        page_type = "listing"
    if page_type == "application" and parser.surface == "account":
        page_type = "account"
    if page_type == "application" and parser.surface == "privacy":
        page_type = "privacy"
    manual_gate = None
    if page_type == "account":
        manual_gate = {
            "type": "account_sign_in",
            "detail": "Sign in or create a profile required",
        }
    if page_type == "privacy":
        manual_gate = {
            "type": "privacy_notice",
            "detail": "Privacy notice acknowledgement required",
        }
    return {
        "page_type": page_type,
        "surface": parser.surface,
        "page_url": page_url,
        "role": parser.role,
        "company": parser.company,
        "location": parser.location,
        "fields": parser.fields,
        "entrypoint": parser.entrypoint,
        "uploaded_resume_verified": None,
        "parser_correction_required": False,
        "manual_gate": manual_gate,
        "confirmation_text": confirmation_text,
        "safe_to_prepare": False,
    }


def main(argv: list[str] | None = None) -> int:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("html_path")
    argument_parser.add_argument("--page-url", required=True)
    argument_parser.add_argument("--expected-resume-basename")
    args = argument_parser.parse_args(argv)
    payload = inspect_html(
        Path(args.html_path).read_text(),
        page_url=args.page_url,
        expected_resume_basename=args.expected_resume_basename,
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
