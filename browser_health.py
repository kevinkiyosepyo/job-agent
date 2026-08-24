#!/usr/bin/env python3
"""CDP browser health checks with recoverable error classification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BASE = Path.home() / "Documents/job-agent"


JsonFetcher = Callable[[str], object]


def fetch_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def classify_browser_error(exc: Exception) -> dict:
    if isinstance(exc, HTTPError):
        recoverable = exc.code >= 500
        return {
            "status": "error",
            "recoverable": recoverable,
            "error_code": f"http_{exc.code}",
            "message": str(exc),
        }
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            return {
                "status": "unreachable",
                "recoverable": True,
                "error_code": "connection_refused",
                "message": str(exc),
            }
        return {
            "status": "unreachable",
            "recoverable": True,
            "error_code": "network_error",
            "message": str(exc),
        }
    return {
        "status": "error",
        "recoverable": False,
        "error_code": exc.__class__.__name__.casefold(),
        "message": str(exc),
    }


def probe_cdp_health(base_url: str, *, fetch_json: JsonFetcher = fetch_json) -> dict:
    normalized = base_url.rstrip("/")
    try:
        version = fetch_json(f"{normalized}/json/version")
        targets = fetch_json(f"{normalized}/json/list")
    except Exception as exc:  # pragma: no cover - covered through public return value tests
        report = classify_browser_error(exc)
        report["base_url"] = normalized
        return report

    browser = version.get("Browser", "") if isinstance(version, dict) else ""
    ws_url = version.get("webSocketDebuggerUrl", "") if isinstance(version, dict) else ""
    raw_targets = targets if isinstance(targets, list) else []
    page_targets = [target for target in raw_targets if isinstance(target, dict) and target.get("type") == "page"]

    if ws_url and page_targets:
        status = "ready"
        recoverable = False
        error_code = None
    elif not ws_url:
        status = "degraded"
        recoverable = True
        error_code = "missing_browser_websocket"
    else:
        status = "degraded"
        recoverable = True
        error_code = "no_page_targets"

    return {
        "status": status,
        "recoverable": recoverable,
        "error_code": error_code,
        "base_url": normalized,
        "browser": browser,
        "websocket_url": ws_url,
        "page_target_count": len(page_targets),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:9222")
    args = parser.parse_args(argv)

    payload = probe_cdp_health(args.base_url)
    print(json.dumps(payload, indent=2))
    return 1 if payload.get("recoverable") else 0


if __name__ == "__main__":
    raise SystemExit(main())
