"""Exact-target, read-only Chrome DevTools Protocol transport.

This module deliberately exposes no navigation, click, typing, upload, or desktop
input APIs. Callers must bind one current ``type == page`` target ID before
reading a small fixed snapshot through CDP.
"""
from __future__ import annotations

import json
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.request import urlopen


JsonFetcher = Callable[[str], object]


class CDPConnection(Protocol):
    def call(self, method: str, params: dict) -> dict: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[[str], CDPConnection]


class TargetBindingError(ValueError):
    """Raised when an exact live Chrome page target cannot be safely bound."""


def fetch_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class WebSocketCDPConnection:
    """Minimal request/response CDP websocket client used only by this transport."""

    def __init__(self, websocket_url: str) -> None:
        import websocket

        self._socket = websocket.create_connection(websocket_url, timeout=20)
        self._sequence = 0

    def call(self, method: str, params: dict) -> dict:
        self._sequence += 1
        request_id = self._sequence
        self._socket.send(json.dumps({"id": request_id, "method": method, "params": params}))
        while True:
            reply = json.loads(self._socket.recv())
            if reply.get("id") != request_id:
                continue
            if "error" in reply:
                raise RuntimeError(reply["error"])
            result = reply.get("result", {})
            if not isinstance(result, dict):
                raise RuntimeError("CDP returned a non-object result")
            return result

    def close(self) -> None:
        self._socket.close()


@dataclass(frozen=True)
class BoundPage(AbstractContextManager["BoundPage"]):
    """A single exact target binding offering fixed read-only snapshot data."""

    target_id: str
    target_url: str
    _connection: CDPConnection
    allowed_cdp_methods: tuple[str, ...] = ("Runtime.evaluate",)

    def _evaluate(self, expression: str) -> str:
        response = self._connection.call(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True}
        )
        result = response.get("result", {})
        if not isinstance(result, dict):
            return ""
        value = result.get("value", "")
        return value if isinstance(value, str) else ""

    def read_only_snapshot(self) -> dict[str, object]:
        """Read fixed page state without allowing page or desktop mutation."""
        return {
            "target_id": self.target_id,
            "target_url": self.target_url,
            "url": self._evaluate("location.href"),
            "title": self._evaluate("document.title"),
            "body_text": self._evaluate("document.body ? document.body.innerText : ''"),
            "html": self._evaluate("document.documentElement ? document.documentElement.outerHTML : ''"),
            "read_only": True,
        }

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self._connection.close()


class ScopedCDPTransport:
    """Bind exactly one current Chrome page target and expose read-only snapshots."""

    def __init__(
        self,
        base_url: str,
        *,
        fetch_json: JsonFetcher = fetch_json,
        connect: ConnectionFactory = WebSocketCDPConnection,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._fetch_json = fetch_json
        self._connect = connect

    def bind_page_target(self, target_id: str) -> BoundPage:
        targets = self._fetch_json(f"{self._base_url}/json/list")
        if not isinstance(targets, list):
            raise TargetBindingError("CDP target list was not an array")

        target = next(
            (
                item
                for item in targets
                if isinstance(item, dict) and item.get("id") == target_id and item.get("type") == "page"
            ),
            None,
        )
        if not isinstance(target, dict):
            raise TargetBindingError("exact page target was not found")

        websocket_url = target.get("webSocketDebuggerUrl")
        target_url = target.get("url")
        if not isinstance(websocket_url, str) or not websocket_url:
            raise TargetBindingError("exact page target has no websocket URL")
        if not isinstance(target_url, str):
            raise TargetBindingError("exact page target has no URL")

        return BoundPage(target_id, target_url, self._connect(websocket_url))

    def bind_mutable_page_target(self, target_id: str):
        """Bind a newly discovered exact page and expose bounded field operations."""
        from mutable_cdp_page_adapter import MutableCDPPageAdapter
        bound = self.bind_page_target(target_id)

        class ManagedAdapter(MutableCDPPageAdapter):
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_value, traceback):
                bound.__exit__(exc_type, exc_value, traceback)

        return ManagedAdapter(target_id=bound.target_id, target_url=bound.target_url, connection=bound._connection)
