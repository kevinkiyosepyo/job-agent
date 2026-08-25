#!/usr/bin/env python3
"""Non-submitting ATS preflight inspector for saved HTML snapshots."""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

import lever_handler
import oracle_handler
from pipeline import validate_confirmation_evidence


class _GreenhouseHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_h1 = False
        self.current_label_text: list[str] | None = None
        self.current_label_closed = False
        self.role = ""
        self.company = ""
        self.location = ""
        self.required_fields: list[str] = []
        self._body_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "h1":
            self.in_h1 = True
        if tag == "label":
            self.current_label_text = []
            self.current_label_closed = False
        if tag in {"input", "select", "textarea"} and self.current_label_text is not None:
            self.current_label_closed = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if tag == "label" and self.current_label_text is not None:
            label = " ".join("".join(self.current_label_text).replace("*", " ").split())
            if label:
                self.required_fields.append(label)
            self.current_label_text = None
            self.current_label_closed = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        self._body_text.append(text)
        if self.in_h1 and not self.role:
            self.role = text
        if self.current_label_text is not None and not self.current_label_closed:
            self.current_label_text.append(text)
        if not self.company and "—" in text:
            company, _, location = text.partition("—")
            self.company = company.strip()
            self.location = location.strip()


class _WorkdayHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_h1 = False
        self.in_h2 = False
        self.role = ""
        self.steps: list[str] = []
        self.current_label_text: list[str] | None = None
        self.fields: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "h1":
            self.in_h1 = True
        if tag == "h2":
            self.in_h2 = True
        if tag == "label":
            self.current_label_text = []
        if tag in {"input", "select", "textarea"} and self.current_label_text is not None:
            self.fields.append(
                {
                    "type": attr_map.get("type") or ("textarea" if tag == "textarea" else tag),
                    "required": "required" in attr_map,
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False
        if tag == "h2":
            self.in_h2 = False
        if tag == "label" and self.current_label_text is not None:
            label = " ".join("".join(self.current_label_text).split())
            if label and self.fields:
                self.fields[-1]["label"] = label
            self.current_label_text = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self.in_h1 and not self.role:
            self.role = text
        if self.in_h2:
            self.steps.append(text)
        if self.current_label_text is not None:
            self.current_label_text.append(text)


def inspect_greenhouse_html(html_text: str, *, page_url: str) -> dict:
    parser = _GreenhouseHTMLParser()
    parser.feed(html_text)
    confirmation_text = None
    page_type = "application"
    try:
        confirmation_text = validate_confirmation_evidence(confirmation_url=page_url, confirmation_text=html_text)
        page_type = "confirmation"
    except ValueError:
        pass
    return {
        "platform": "greenhouse",
        "page_url": page_url,
        "page_type": page_type,
        "company": parser.company,
        "role": parser.role,
        "location": parser.location,
        "required_fields": parser.required_fields,
        "manual_gate": None,
        "confirmation_text": confirmation_text,
    }


def inspect_workday_html(html_text: str, *, page_url: str) -> dict:
    parser = _WorkdayHTMLParser()
    parser.feed(html_text)
    confirmation_text = None
    page_type = "application"
    try:
        confirmation_text = validate_confirmation_evidence(confirmation_url=page_url, confirmation_text=html_text)
        page_type = "confirmation"
    except ValueError:
        pass
    return {
        "platform": "workday",
        "page_url": page_url,
        "page_type": page_type,
        "role": parser.role,
        "steps": parser.steps,
        "fields": parser.fields,
        "manual_gate": None,
        "confirmation_text": confirmation_text,
    }


def inspect_target(target: dict, *, read_text: Callable[[Path], str] | None = None) -> dict:
    loader = read_text or (lambda path: path.read_text())
    html_text = loader(Path(target["html_path"]))
    platform = target["platform"]
    page_url = target["page_url"]
    if platform == "greenhouse":
        return inspect_greenhouse_html(html_text, page_url=page_url)
    if platform == "workday":
        return inspect_workday_html(html_text, page_url=page_url)
    if platform == "lever":
        result = lever_handler.inspect_html(
            html_text,
            page_url=page_url,
            expected_resume_basename=target.get("expected_resume_basename"),
        )
        result["platform"] = "lever"
        return result
    if platform == "oracle":
        result = oracle_handler.inspect_html(
            html_text,
            page_url=page_url,
            expected_resume_basename=target.get("expected_resume_basename"),
        )
        result["platform"] = "oracle"
        return result
    raise ValueError(f"Unsupported platform: {platform}")


def run_preflight_manifest(manifest: list[dict]) -> dict:
    results = [inspect_target(target) for target in manifest]
    return {
        "results": results,
        "summary": {
            "target_count": len(results),
            "application_count": sum(result.get("page_type") == "application" for result in results),
            "confirmation_count": sum(result.get("page_type") == "confirmation" for result in results),
            "manual_gate_count": sum(result.get("manual_gate") is not None for result in results),
            "failure_count": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest_path")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    payload = run_preflight_manifest(json.loads(Path(args.manifest_path).read_text()))
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
