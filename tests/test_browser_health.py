from __future__ import annotations

import sys
from pathlib import Path
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import browser_health


@pytest.mark.parametrize("code", [401, 403, 404, 500])
def test_main_returns_failure_for_http_errors(monkeypatch, code):
    from urllib.error import HTTPError

    monkeypatch.setattr(browser_health, "probe_cdp_health", lambda url:
                        browser_health.classify_browser_error(HTTPError(url, code, "failed", {}, None)))
    assert browser_health.main([]) == 1


@pytest.mark.parametrize("outcome,expected", [
    ({"status": "ready", "verified": True}, "ready"),
    ({"status": "ready", "verified": False}, "degraded"),
    (TimeoutError("private diagnostic"), "error"),
    (None, "unavailable"),
])
def test_transport_probe_calls_actual_injected_transport(outcome, expected):
    calls = []
    def caller():
        calls.append("executor transport")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    assert hasattr(browser_health, "probe_transport_health")
    report = browser_health.probe_transport_health(caller=caller if outcome is not None else None)
    assert report["status"] == expected
    assert calls == ([] if outcome is None else ["executor transport"])
    assert "private diagnostic" not in str(report)


def test_probe_reports_ready_when_version_and_page_targets_exist():
    def fetch_json(url: str):
        if url.endswith("/json/version"):
            return {
                "Browser": "Chrome/139.0",
                "Protocol-Version": "1.3",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/abc",
            }
        if url.endswith("/json/list"):
            return [
                {"id": "page-1", "type": "page", "title": "Example", "url": "https://example.com"}
            ]
        raise AssertionError(f"unexpected url: {url}")

    report = browser_health.probe_cdp_health("http://127.0.0.1:9222", fetch_json=fetch_json)

    assert report["status"] == "ready"
    assert report["recoverable"] is False
    assert report["browser"] == "Chrome/139.0"
    assert report["page_target_count"] == 1


def test_probe_classifies_connection_refused_as_recoverable():
    def fetch_json(url: str):
        raise URLError(ConnectionRefusedError(61, "Connection refused"))

    report = browser_health.probe_cdp_health("http://127.0.0.1:9222/", fetch_json=fetch_json)

    assert report["status"] == "unreachable"
    assert report["recoverable"] is True
    assert report["error_code"] == "connection_refused"
    assert report["base_url"] == "http://127.0.0.1:9222"


def test_main_returns_one_and_emits_json_for_recoverable_health_issue(monkeypatch, capsys):
    monkeypatch.setattr(
        browser_health,
        "probe_cdp_health",
        lambda base_url, fetch_json=browser_health.fetch_json: {
            "status": "unreachable",
            "recoverable": True,
            "error_code": "connection_refused",
            "base_url": base_url,
        },
    )

    exit_code = browser_health.main(["--base-url", "http://127.0.0.1:9222"])

    assert exit_code == 1
    payload = capsys.readouterr().out
    assert '"status": "unreachable"' in payload
    assert '"error_code": "connection_refused"' in payload
