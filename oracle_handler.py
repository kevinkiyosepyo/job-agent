#!/usr/bin/env python3
"""Fixture-driven Oracle Recruiting application inspector."""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

from pipeline import validate_confirmation_evidence


class _OracleHTMLParser(HTMLParser):
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
        self.issues: list[dict[str, str]] = []
        self._current_combo: dict | None = None
        self._combo_option_depth = 0
        self._location_depth = 0
        self._current_issue_target: str | None = None
        self._current_issue_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "h1":
            self.in_h1 = True
        if tag == "label":
            self.current_label_for = attr_map.get("for")
            self.current_label_text = []
        if tag == "a" and (attr_map.get("href") or "").startswith("#"):
            self._current_issue_target = (attr_map.get("href") or "")[1:]
            self._current_issue_text = []
        if attr_map.get("class") == "job-location":
            self._location_depth += 1
        if tag == "input":
            field_id = attr_map.get("id") or ""
            self.fields.append(
                {
                    "label": self.label_by_id.get(field_id, ""),
                    "name": attr_map.get("name") or field_id,
                    "type": attr_map.get("type") or "text",
                    "required": "required" in attr_map,
                }
            )
            uploaded = attr_map.get("data-uploaded-filename")
            if uploaded:
                self.uploaded_names.append(uploaded)
        if tag == "div" and attr_map.get("data-field-type") == "combobox":
            self._current_combo = {
                "label": self.label_by_id.get(attr_map.get("name") or "", ""),
                "name": attr_map.get("data-name") or attr_map.get("name") or "",
                "type": "combobox",
                "required": (attr_map.get("data-required") or "").lower() == "true",
                "value": attr_map.get("data-value") or "",
                "options": [],
            }
            self.fields.append(self._current_combo)
        if tag == "li" and self._current_combo is not None:
            self._combo_option_depth += 1

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
        if tag == "a" and self._current_issue_text is not None and self._current_issue_target is not None:
            message = " ".join("".join(self._current_issue_text).split())
            if message:
                self.issues.append({"message": message, "target": self._current_issue_target})
            self._current_issue_target = None
            self._current_issue_text = None
        if tag == "li" and self._combo_option_depth:
            self._combo_option_depth -= 1
        if tag == "div" and self._current_combo is not None:
            combo_name = self._current_combo["name"]
            self._current_combo["label"] = self.label_by_id.get(combo_name, self._current_combo["label"])
            self._current_combo = None
        if tag == "div" and self._location_depth:
            self._location_depth -= 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_h1 and not self.role:
            self.role = text
        if self.current_label_text is not None:
            self.current_label_text.append(text)
        if self._current_issue_text is not None:
            self._current_issue_text.append(text)
        if self._location_depth and not self.location:
            self.location = text
        if self._current_combo is not None and self._combo_option_depth:
            self._current_combo["options"].append(text)
        if text.lower().endswith((".pdf", ".doc", ".docx")):
            self.uploaded_names.append(text)


def inspect_html(html_text: str, *, page_url: str, expected_resume_basename: str | None = None) -> dict:
    parser = _OracleHTMLParser()
    parser.feed(html_text)
    uploaded_resume_verified = None
    if expected_resume_basename is not None:
        uploaded_resume_verified = expected_resume_basename in parser.uploaded_names
    country_field = next((field for field in parser.fields if field.get("name") == "country"), None)
    salary_field = next((field for field in parser.fields if field.get("name") == "salary"), None)
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
        "role": parser.role,
        "location": parser.location,
        "fields": parser.fields,
        "uploaded_resume_verified": uploaded_resume_verified,
        "country_valid": country_field is not None and country_field.get("value") == "United States",
        "salary_selected": salary_field.get("value") if salary_field else None,
        "issues": parser.issues,
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
