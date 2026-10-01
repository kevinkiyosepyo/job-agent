"""Bounded real-Chrome CAPTCHA checkbox attempt; never fabricates clearance.

Only a visible provider checkbox may be clicked once. Image/audio challenges,
managed challenges and absent provider responses remain blocking. The caller
must also re-inspect the exact application page before preparing/submitting.
"""
from __future__ import annotations

import time
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urlsplit


class CDPConnection(Protocol):
    def call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...


def has_provider_frame(html_text: str) -> bool:
    """Find candidate provider frames in saved HTML; never treat this as a gate."""
    class FrameScanner(HTMLParser):
        found = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag != 'iframe':
                return
            src = dict(attrs).get('src') or ''
            parts = urlsplit('https:' + src if src.startswith('//') else src)
            host = parts.hostname or ''
            if parts.scheme == 'https' and (
                (host in {'google.com', 'www.google.com', 'recaptcha.net', 'www.recaptcha.net'}
                 and '/recaptcha/' in parts.path)
                or (host == 'hcaptcha.com' or host.endswith('.hcaptcha.com'))
                or host == 'challenges.cloudflare.com'
            ):
                self.found = True

    scanner = FrameScanner()
    scanner.feed(html_text)
    return scanner.found


_DETECT_JS = r"""(() => { // _captcha_probe
    const visible = el => {
        if (!el) return false;
        const s = getComputedStyle(el), r = el.getBoundingClientRect();
        return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
    };
    const provider = (el, host, path) => {
        try { const u = new URL(el.src); return u.protocol === 'https:' &&
            (u.hostname === host || u.hostname.endsWith('.' + host)) &&
            (!path || u.pathname.includes(path)); } catch (_) { return false; }
    };
    const frames = [...document.querySelectorAll('iframe[src]')].filter(visible);
    const rc = frames.filter(f => provider(f, 'google.com', '/recaptcha/') || provider(f, 'recaptcha.net', '/recaptcha/'));
    const hc = frames.filter(f => provider(f, 'hcaptcha.com', ''));
    const ts = frames.filter(f => provider(f, 'challenges.cloudflare.com', '/'));
    const token = selector => {
        const value = document.querySelector(selector)?.value;
        return typeof value === 'string' && value.length > 20;
    };
    if (hc.length || ts.length || rc.length > 1 ||
        (rc.length === 1 && !new URL(rc[0].src).pathname.includes('/anchor')))
        return {detected: true, kind: 'unsupported_challenge', cleared: false};
    if (rc.length === 1) return {detected: true, kind: 'recaptcha_v2',
        cleared: token('textarea[name="g-recaptcha-response"]')};
    if (document.querySelector('.grecaptcha-badge, textarea[name="g-recaptcha-response"]'))
        return {detected: true, kind: 'recaptcha_invisible', cleared: false};
    return {detected: false, kind: null, cleared: false};
})()"""

_CHECKBOX_JS = r"""(() => { // _captcha_checkbox
    const allowed = f => {
        try { const u = new URL(f.src), h = u.hostname;
            return u.protocol === 'https:' &&
                (h === 'google.com' || h.endsWith('.google.com') || h === 'recaptcha.net' || h.endsWith('.recaptcha.net')) &&
                u.pathname.includes('/recaptcha/') && u.pathname.includes('/anchor');
        } catch (_) { return false; }
    };
    const allFrames = [...document.querySelectorAll('iframe[src]')];
    if (allFrames.some(f => {
        try {
            const u = new URL(f.src), h = u.hostname, r = f.getBoundingClientRect(), s = getComputedStyle(f);
            if (s.display === 'none' || s.visibility === 'hidden' || !r.width || !r.height) return false;
            return (u.protocol === 'https:' && ((h === 'hcaptcha.com' || h.endsWith('.hcaptcha.com')) ||
                h === 'challenges.cloudflare.com' ||
                (((h === 'google.com' || h.endsWith('.google.com') || h === 'recaptcha.net' || h.endsWith('.recaptcha.net')) &&
                  u.pathname.includes('/recaptcha/') && !u.pathname.includes('/anchor')))));
        } catch (_) { return false; }
    })) return {found: false};
    const frames = allFrames.filter(allowed).filter(f => {
        const r = f.getBoundingClientRect(), s = getComputedStyle(f);
        return s.display !== 'none' && s.visibility !== 'hidden' && r.width >= 40 && r.width <= 330 && r.height >= 35 && r.height <= 110;
    });
    if (frames.length !== 1) return {found: false};
    const f = frames[0], r = f.getBoundingClientRect();
    const x = Math.round(r.left + Math.min(28, r.width / 5)), y = Math.round(r.top + r.height / 2);
    if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight || document.elementFromPoint(x, y) !== f)
        return {found: false};
    return {found: true, x, y};
})()"""


def _value(conn: CDPConnection, expression: str) -> Any:
    response = conn.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    if not isinstance(response, dict) or response.get("exceptionDetails") or not isinstance(response.get("result"), dict):
        raise ValueError("CAPTCHA page observation unavailable")
    return response["result"].get("value")


def detect(conn: CDPConnection) -> dict[str, Any]:
    """Read actual provider-response presence, not its secret token contents."""
    value = _value(conn, _DETECT_JS)
    if not isinstance(value, dict) or not all(type(value.get(k)) is bool for k in ("detected", "cleared")):
        raise ValueError("CAPTCHA detection returned invalid evidence")
    return {"detected": value["detected"], "kind": value.get("kind"), "cleared": value["cleared"]}


def attempt_solve(conn: CDPConnection, *, expected_url: str, timeout: float = 12.0,
                  poll_interval: float = 0.25) -> dict[str, Any]:
    """Click one exact-target checkbox and wait for provider-issued response.

    A positive result is not submission authorization: the caller must still
    read back the same page and ensure every application gate has cleared.
    """
    result: dict[str, Any] = {"solved": False, "kind": None, "attempts": 0, "detail": "unverified"}
    try:
        if not expected_url or _value(conn, "location.href") != expected_url:
            return {**result, "detail": "target_drift"}
        state = detect(conn)
        kind = state.get("kind")
        result["kind"] = kind
        if not state["detected"]:
            return {**result, "detail": "no_visible_widget"}
        if kind != "recaptcha_v2":
            return {**result, "detail": "unsupported_challenge"}
        if state["cleared"]:
            return {**result, "solved": True, "detail": "provider_response_present"}
        target = _value(conn, _CHECKBOX_JS)
        if not isinstance(target, dict) or target.get("found") is not True or not all(
                isinstance(target.get(k), int) for k in ("x", "y")):
            return {**result, "detail": "checkbox_not_safely_clickable"}
        if _value(conn, "location.href") != expected_url:
            return {**result, "detail": "target_drift"}
        for action in ("mousePressed", "mouseReleased"):
            conn.call("Input.dispatchMouseEvent", {"type": action, "x": target["x"], "y": target["y"],
                                                   "button": "left", "clickCount": 1})
        result["attempts"] = 1
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if _value(conn, "location.href") != expected_url:
                return {**result, "detail": "target_changed_after_click"}
            current = detect(conn)
            if current.get("kind") == kind and current.get("cleared") is True:
                return {**result, "solved": True, "detail": "provider_response_present"}
            if time.monotonic() >= deadline:
                return {**result, "detail": "challenge_not_cleared"}
            time.sleep(max(0.0, poll_interval))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        return {**result, "detail": "observation_or_click_failed"}
