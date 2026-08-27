from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_bind_exact_page_target_and_capture_read_only_snapshot():
    import scoped_cdp

    requested_target_id = "page-42"
    fetched_urls: list[str] = []
    calls: list[tuple[str, dict]] = []

    def fetch_json(url: str) -> object:
        fetched_urls.append(url)
        return [
            {
                "id": requested_target_id,
                "type": "page",
                "url": "https://careers.example.test/apply",
                "title": "Example careers",
                "webSocketDebuggerUrl": "ws://127.0.0.1:18800/devtools/page/page-42",
            },
            {
                "id": "worker-7",
                "type": "service_worker",
                "webSocketDebuggerUrl": "ws://127.0.0.1:18800/devtools/page/worker-7",
            },
        ]

    class FakeConnection:
        def call(self, method: str, params: dict) -> dict:
            calls.append((method, params))
            values = {
                "location.href": "https://careers.example.test/apply",
                "document.title": "Example careers",
                "document.body ? document.body.innerText : ''": "Apply now",
                "document.documentElement ? document.documentElement.outerHTML : ''": "<html>Apply now</html>",
            }
            return {"result": {"value": values[params["expression"]]}}

        def close(self) -> None:
            calls.append(("close", {}))

    opened_urls: list[str] = []

    def connect(websocket_url: str) -> FakeConnection:
        opened_urls.append(websocket_url)
        return FakeConnection()

    transport = scoped_cdp.ScopedCDPTransport(
        "http://127.0.0.1:18800",
        fetch_json=fetch_json,
        connect=connect,
    )

    with transport.bind_page_target(requested_target_id) as page:
        snapshot = page.read_only_snapshot()

    assert fetched_urls == ["http://127.0.0.1:18800/json/list"]
    assert opened_urls == ["ws://127.0.0.1:18800/devtools/page/page-42"]
    assert calls == [
        ("Runtime.evaluate", {"expression": "location.href", "returnByValue": True}),
        ("Runtime.evaluate", {"expression": "document.title", "returnByValue": True}),
        ("Runtime.evaluate", {"expression": "document.body ? document.body.innerText : ''", "returnByValue": True}),
        ("Runtime.evaluate", {"expression": "document.documentElement ? document.documentElement.outerHTML : ''", "returnByValue": True}),
        ("close", {}),
    ]
    assert snapshot == {
        "target_id": requested_target_id,
        "target_url": "https://careers.example.test/apply",
        "url": "https://careers.example.test/apply",
        "title": "Example careers",
        "body_text": "Apply now",
        "html": "<html>Apply now</html>",
        "read_only": True,
    }
    assert page.allowed_cdp_methods == ("Runtime.evaluate",)


def test_bind_rejects_non_page_or_unknown_target_without_connecting():
    import scoped_cdp

    def fetch_json(url: str) -> object:
        return [{"id": "worker-7", "type": "service_worker", "webSocketDebuggerUrl": "ws://worker"}]

    transport = scoped_cdp.ScopedCDPTransport(
        "http://127.0.0.1:18800",
        fetch_json=fetch_json,
        connect=lambda websocket_url: pytest.fail("must not connect"),
    )

    with pytest.raises(scoped_cdp.TargetBindingError, match="exact page target was not found"):
        transport.bind_page_target("worker-7")
