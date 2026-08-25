#!/usr/bin/env python3
"""Fixture-driven Lever application inspector."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from pipeline import validate_confirmation_evidence


class _LeverHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_h1 = False
        self.current_label_for: str | None = None
        self.current_label_text: list[str] | None = None
        self.role = ""
        self.location = ""
        self.fields: list[dict] = []
        self.label_by_id: dict[str, str] = {}
        self.uploaded_names: list[str] = []
        self.text_chunks: list[str] = []
        self._location_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        classes = set((attr_map.get("class") or "").split())
        if tag == "h1":
            self.in_h1 = True
        if tag == "label":
            self.current_label_for = attr_map.get("for")
            self.current_label_text = []
        if "sort-by-location" in classes:
            self._location_depth += 1
        if tag in {"input", "textarea", "select"}:
            field_id = attr_map.get("id") or ""
            field_type = attr_map.get("type") or ("textarea" if tag == "textarea" else tag)
            self.fields.append(
                {
                    "label": self.label_by_id.get(field_id, ""),
                    "name": attr_map.get("name") or field_id,
                    "type": field_type,
                    "required": "required" in attr_map,
                }
            )
            uploaded = attr_map.get("data-uploaded-filename")
            if uploaded:
                self.uploaded_names.append(uploaded)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if tag == "label" and self.current_label_text is not None:
            label = " ".join("".join(self.current_label_text).split())
            if self.current_label_for:
                self.label_by_id[self.current_label_for] = label
                for field in self.fields:
                    if field["name"] == self.current_label_for:
                        field["label"] = label
            self.current_label_for = None
            self.current_label_text = None
        if self._location_depth and tag in {"span", "div"}:
            self._location_depth -= 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        self.text_chunks.append(text)
        if self.in_h1 and not self.role:
            self.role = text
        if self.current_label_text is not None:
            self.current_label_text.append(text)
        if self._location_depth and not self.location:
            self.location = text
        if text.lower().endswith((".pdf", ".doc", ".docx")):
            self.uploaded_names.append(text)


def _company_from_url(page_url: str) -> str:
    match = re.search(r"jobs\.lever\.co/([^/]+)", page_url)
    if match:
        token = match.group(1).replace("-", " ").replace("_", " ").strip()
        return " ".join(part.capitalize() for part in token.split())
    host = urlparse(page_url).netloc
    return host or "Unknown"


def _detect_manual_gate(text_chunks: list[str]) -> dict | None:
    lowered = " ".join(text_chunks).casefold()
    if "captcha" in lowered or "hcaptcha" in lowered or "recaptcha" in lowered:
        return {"type": "captcha", "detail": "CAPTCHA detected"}
    return None


def inspect_html(html_text: str, *, page_url: str, expected_resume_basename: str | None = None) -> dict:
    parser = _LeverHTMLParser()
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
        "company": _company_from_url(page_url),
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
