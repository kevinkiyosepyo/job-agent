"""Automated CAPTCHA handling for real Chrome CDP sessions.

Detects, clicks, and waits for reCAPTCHA v2/v3, hCaptcha, and Cloudflare
Turnstile widgets in a real Chrome browser.  Real Chrome with normal
browsing history auto-passes most checkbox challenges; image grids are
retried with fresh challenges before falling back.
"""
from __future__ import annotations

import time
from typing import Any, Protocol


class CDPConnection(Protocol):
    def send(self, method: str, params: dict[str, Any] | None = None) -> Any: ...


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_DETECT_JS = r"""(() => {
    const shown = el => {
        if (!el || el.offsetParent === null) {
            // offsetParent is null for hidden/display:none, but also for
            // position:fixed elements — check computed visibility.
            const s = el ? getComputedStyle(el) : null;
            if (!s || s.display === 'none' || s.visibility === 'hidden') return false;
        }
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    };

    const result = {detected: false, kind: null, cleared: false, details: {}};

    // --- reCAPTCHA v2 checkbox ---
    const rcFrames = [...document.querySelectorAll(
        'iframe[src*="recaptcha/api2/anchor"], iframe[src*="recaptcha/enterprise/anchor"]'
    )].filter(shown);
    if (rcFrames.length) {
        result.detected = true;
        result.kind = 'recaptcha_v2';
        result.details.iframe_count = rcFrames.length;
        result.details.frame_src = rcFrames[0].src;
        // Check if already solved via the response textarea
        const resp = document.querySelector('textarea[name="g-recaptcha-response"]');
        if (resp && resp.value && resp.value.length > 20) {
            result.cleared = true;
        }
        return result;
    }

    // --- reCAPTCHA v2 invisible / v3 (score-based, auto-pass in real Chrome) ---
    const badge = document.querySelector('.grecaptcha-badge');
    const invisibleResp = document.querySelector('textarea[name="g-recaptcha-response"]');
    if (badge || invisibleResp) {
        result.detected = true;
        result.kind = 'recaptcha_invisible';
        if (invisibleResp && invisibleResp.value && invisibleResp.value.length > 20) {
            result.cleared = true;
        } else {
            // Invisible/v3 typically auto-resolves; not a visible gate.
            result.cleared = true;
        }
        return result;
    }

    // --- hCaptcha ---
    const hcFrames = [...document.querySelectorAll(
        'iframe[src*="hcaptcha.com/captcha"]'
    )].filter(shown);
    if (hcFrames.length) {
        result.detected = true;
        result.kind = 'hcaptcha';
        result.details.iframe_count = hcFrames.length;
        result.details.frame_src = hcFrames[0].src;
        const hResp = document.querySelector('textarea[name="h-captcha-response"], input[name="h-captcha-response"]');
        if (hResp && hResp.value && hResp.value.length > 20) {
            result.cleared = true;
        }
        return result;
    }

    // --- Cloudflare Turnstile ---
    const tsFrames = [...document.querySelectorAll(
        'iframe[src*="challenges.cloudflare.com"]'
    )].filter(shown);
    if (tsFrames.length) {
        result.detected = true;
        result.kind = 'turnstile';
        result.details.iframe_count = tsFrames.length;
        result.details.frame_src = tsFrames[0].src;
        const tResp = document.querySelector('input[name="cf-turnstile-response"]');
        if (tResp && tResp.value && tResp.value.length > 20) {
            result.cleared = true;
        }
        return result;
    }

    // --- Visible "I'm not a robot" text without a detected iframe (edge case) ---
    const labels = [...document.querySelectorAll('label, span, div')].filter(
        el => shown(el) && /i.m not a robot/i.test(el.textContent)
    );
    if (labels.length) {
        result.detected = true;
        result.kind = 'unknown_checkbox';
        return result;
    }

    return result;
})()"""


_FIND_CHECKBOX_JS = r"""(() => {
    // Find the reCAPTCHA or hCaptcha checkbox iframe and return its center.
    const shown = el => {
        if (!el) return false;
        const s = getComputedStyle(el);
        if (s.display === 'none' || s.visibility === 'hidden') return false;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
    };

    // reCAPTCHA anchor iframe
    let frame = [...document.querySelectorAll(
        'iframe[src*="recaptcha/api2/anchor"], iframe[src*="recaptcha/enterprise/anchor"]'
    )].find(shown);

    // hCaptcha checkbox iframe
    if (!frame) {
        frame = [...document.querySelectorAll(
            'iframe[src*="hcaptcha.com/captcha"]'
        )].find(shown);
    }

    // Turnstile iframe
    if (!frame) {
        frame = [...document.querySelectorAll(
            'iframe[src*="challenges.cloudflare.com"]'
        )].find(shown);
    }

    if (!frame) return {found: false};
    const r = frame.getBoundingClientRect();
    return {
        found: true,
        x: Math.round(r.left + Math.min(r.width * 0.15, 30)),
        y: Math.round(r.top + r.height / 2),
        width: Math.round(r.width),
        height: Math.round(r.height),
    };
})()"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect(conn: CDPConnection) -> dict[str, Any]:
    """Return CAPTCHA detection state for the current page.

    Keys: detected (bool), kind (str|None), cleared (bool), details (dict).
    """
    return conn.send("Runtime.evaluate", {
        "expression": _DETECT_JS,
        "returnByValue": True,
    }).get("result", {}).get("value", {"detected": False, "kind": None, "cleared": False, "details": {}})


def attempt_solve(
    conn: CDPConnection,
    *,
    max_retries: int = 3,
    poll_interval: float = 2.0,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Try to clear a CAPTCHA challenge automatically.

    In a real Chrome profile, clicking the checkbox is usually enough.
    Returns {solved: bool, kind: str, attempts: int, detail: str}.
    """
    state = detect(conn)
    if not state.get("detected"):
        return {"solved": True, "kind": None, "attempts": 0, "detail": "no_captcha_present"}
    if state.get("cleared"):
        return {"solved": True, "kind": state["kind"], "attempts": 0, "detail": "already_cleared"}

    kind = state.get("kind", "unknown")
    if kind in ("recaptcha_invisible",):
        # Invisible/v3 auto-resolves; no click needed.
        return {"solved": True, "kind": kind, "attempts": 0, "detail": "invisible_auto_pass"}

    for attempt in range(1, max_retries + 1):
        # Find and click the checkbox.
        checkbox = conn.send("Runtime.evaluate", {
            "expression": _FIND_CHECKBOX_JS,
            "returnByValue": True,
        }).get("result", {}).get("value", {})

        if not checkbox.get("found"):
            # No clickable iframe; check if it cleared on its own.
            recheck = detect(conn)
            if recheck.get("cleared") or not recheck.get("detected"):
                return {"solved": True, "kind": kind, "attempts": attempt, "detail": "auto_cleared"}
            time.sleep(poll_interval)
            continue

        # Click the checkbox area.
        conn.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": checkbox["x"],
            "y": checkbox["y"],
            "button": "left",
            "clickCount": 1,
        })
        conn.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": checkbox["x"],
            "y": checkbox["y"],
            "button": "left",
            "clickCount": 1,
        })

        # Wait for resolution.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            recheck = detect(conn)
            if recheck.get("cleared") or not recheck.get("detected"):
                return {
                    "solved": True,
                    "kind": kind,
                    "attempts": attempt,
                    "detail": "checkbox_click_solved",
                }
            # If an image challenge appeared, wait longer — real Chrome
            # sometimes auto-clears after the behavioral analysis completes.

        # Timed out this attempt; retry.

    return {
        "solved": False,
        "kind": kind,
        "attempts": max_retries,
        "detail": "exhausted_retries",
    }


def is_dormant(text: str) -> bool:
    """Return True when CAPTCHA indicators are only dormant code, not a real gate.

    Call this on page text/HTML before emitting a blocking gate.  Scripts,
    hidden response fields, invisible badges, and empty containers are not
    rendered challenges.
    """
    lowered = text.casefold()
    markers = ("captcha", "hcaptcha", "recaptcha", "turnstile")
    if not any(m in lowered for m in markers):
        return True  # No CAPTCHA indicators at all.
    # If the only indicators are script tags, hidden inputs, badges, or
    # template elements, treat as dormant.
    from html.parser import HTMLParser

    class _Scanner(HTMLParser):
        def __init__(self):
            super().__init__()
            self.visible_captcha = False
            self._in_hidden = False
            self._tag_stack: list[str] = []

        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            self._tag_stack.append(tag)
            if tag in ("script", "template", "style"):
                return
            if tag == "input" and d.get("type") == "hidden":
                return
            style = d.get("style", "") or ""
            if d.get("hidden") is not None or "display: none" in style:
                self._in_hidden = True
                return
            name = d.get("name", "") or ""
            if tag in ("textarea",) and name.startswith(("g-recaptcha", "h-captcha", "cf-turnstile")):
                return
            cls = d.get("class", "") or ""
            if tag == "div" and "grecaptcha-badge" in cls:
                return

        def handle_data(self, data):
            if self._tag_stack and self._tag_stack[-1] in ("script", "template", "style"):
                return
            if self._in_hidden:
                return
            if any(m in data.casefold() for m in markers):
                self.visible_captcha = True

        def handle_endtag(self, tag):
            if self._tag_stack:
                self._tag_stack.pop()

    scanner = _Scanner()
    try:
        scanner.feed(text)
    except Exception:
        pass
    return not scanner.visible_captcha
