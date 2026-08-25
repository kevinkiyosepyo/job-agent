#!/usr/bin/env python3
"""Fixture-driven Greenhouse application inspector."""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

from pipeline import validate_confirmation_evidence


class _GreenhouseHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_h1 = False
        self.current_field: dict | None = None
        self.current_label_text: list[str] | None = None
        self.current_label_closed = False
        self.role = ""
        self.company = ""
        self.location = ""
        self.fields: list[dict] = []
        self.uploaded_names: list[str] = []
        self.text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "h1":
            self.in_h1 = True
        if tag == "label":
            self.current_label_text = []
            self.current_field = None
            self.current_label_closed = False
        if tag in {"input", "select", "textarea"} and self.current_label_text is not None:
            self.current_label_closed = True
            field_type = attr_map.get("type") or ("textarea" if tag == "textarea" else tag)
            self.current_field = {
                "label": "",
                "name": attr_map.get("name") or attr_map.get("id") or "",
                "type": field_type,
                "required": "required" in attr_map,
            }
            self.fields.append(self.current_field)
            uploaded = attr_map.get("data-uploaded-filename")
            if uploaded:
                self.uploaded_names.append(uploaded)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if tag == "label" and self.current_label_text is not None:
            label = " ".join("".join(self.current_label_text).replace("*", " ").split())
            if self.current_field is not None:
                self.current_field["label"] = label
            self.current_label_text = None
            self.current_field = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        self.text_chunks.append(text)
        if self.in_h1 and not self.role:
            self.role = text
        if self.current_label_text is not None and not self.current_label_closed:
            self.current_label_text.append(text)
        if not self.company and "—" in text:
            company, _, location = text.partition("—")
            self.company = company.strip()
            self.location = location.strip()
        if text.lower().endswith((".pdf", ".doc", ".docx")):
            self.uploaded_names.append(text)


def _detect_manual_gate(text_chunks: list[str]) -> dict | None:
    lowered = " ".join(text_chunks).casefold()
    if "captcha" in lowered or "hcaptcha" in lowered or "recaptcha" in lowered:
        return {"type": "captcha", "detail": "CAPTCHA detected"}
    return None


def inspect_html(html_text: str, *, page_url: str, expected_resume_basename: str | None = None) -> dict:
    parser = _GreenhouseHTMLParser()
    parser.feed(html_text)
    uploaded_resume_verified = None
    if expected_resume_basename is not None:
        uploaded_resume_verified = expected_resume_basename in parser.uploaded_names
    manual_gate = _detect_manual_gate(parser.text_chunks)
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
    return {
        "page_type": page_type,
        "page_url": page_url,
        "company": parser.company,
        "role": parser.role,
        "location": parser.location,
        "fields": parser.fields,
        "uploaded_resume_verified": uploaded_resume_verified,
        "manual_gate": manual_gate,
        "confirmation_text": confirmation_text,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html_path")
    parser.add_argument("--page-url", required=True)
    parser.add_argument("--expected-resume-basename")
    args = parser.parse_args(argv)

    payload = inspect_html(
        Path(args.html_path).read_text(),
        page_url=args.page_url,
        expected_resume_basename=args.expected_resume_basename,
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
