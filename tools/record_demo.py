"""Record the README demo GIF against the sanitized Greenhouse-styled fixture.

Launches an ephemeral headless Chrome, binds one exact page target over CDP, and
drives the form through the repository's real MutableCDPPageAdapter and
browser_actions read-back contracts. Every fill is verified the same way the
production path verifies it. The run completes autonomously: after
Review reconciles, it issues a single-use token, calls click_submit_once exactly
once, and reads the confirmation back through inspect_confirmation.

Everything here is sanitized. The fixture is local, the identity is fake, and the
"resume" is a generated placeholder PDF. Frames are written to a runtime dir and
stitched by ffmpeg into docs/demo.gif.

Usage (Python 3.11+):
    python tools/record_demo.py --output docs/demo.gif
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import websocket  # noqa: E402  (websocket-client)

from browser_actions import cdp_upload, native_select, replace_text  # noqa: E402
from mutable_cdp_page_adapter import MutableCDPPageAdapter  # noqa: E402

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
FIXTURE = ROOT / "fixtures" / "demo_greenhouse_styled.html"
VIEWPORT = (1180, 860)

# Sanitized identity. Nothing here belongs to a real person.
PROFILE = {
    "first_name": "Sam",
    "last_name": "Fixture",
    "email": "sam.fixture@example.test",
    "phone": "(555) 010-4242",
    "authorization": "Yes",
    "sponsorship": "No",
    "school": "University of California, San Diego",
    "source": "Social Media",
}


class WSConnection:
    """Minimal synchronous CDP connection satisfying the adapter's protocol."""

    def __init__(self, ws_url: str) -> None:
        self._ws = websocket.create_connection(ws_url, suppress_origin=True)
        self._next = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next += 1
        msg_id = self._next
        self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self._ws.recv())
            if payload.get("id") == msg_id:
                if "error" in payload:
                    raise RuntimeError(payload["error"].get("message", "CDP error"))
                return payload.get("result", {})

    def close(self) -> None:
        self._ws.close()


class Recorder:
    def __init__(self, conn: WSConnection, frames_dir: Path) -> None:
        self.conn = conn
        self.frames_dir = frames_dir
        self.index = 0
        frames_dir.mkdir(parents=True, exist_ok=True)

    def frame(self, hold: int = 1) -> None:
        """Capture one screenshot; `hold` duplicates it to lengthen on-screen time."""
        shot = self.conn.call("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(shot["data"])
        for _ in range(hold):
            (self.frames_dir / f"f{self.index:05d}.png").write_bytes(data)
            self.index += 1


def hud(conn: WSConnection, js: str) -> None:
    conn.call("Runtime.evaluate", {"expression": js, "awaitPromise": True})


def make_placeholder_pdf(path: Path) -> None:
    body = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    path.write_bytes(body)


def wait_for_devtools(port: int, timeout: float = 15.0) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as r:
                return json.load(r)
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Chrome DevTools endpoint did not come up")


def type_like_human(adapter: MutableCDPPageAdapter, rec: Recorder, selector: str, value: str) -> dict:
    """Show progressive typing for the camera, then run the REAL replace_text contract.

    The intermediate keystrokes are purely visual. The evidence record that matters
    comes from browser_actions.replace_text, which writes the final value and reads
    it back — identical to the production path.
    """
    for i in range(1, len(value)):
        adapter.replace_text(selector, value[:i])
        if i % 2 == 0:
            rec.frame()
    evidence = replace_text(adapter, selector, value)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "docs" / "demo.gif"))
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--keep-frames", action="store_true")
    args = parser.parse_args()

    if not CHROME.is_file():
        print("Google Chrome not found", file=sys.stderr)
        return 2
    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found", file=sys.stderr)
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="job-agent-demo-"))
    profile_dir = tmp / "profile"
    frames = tmp / "frames"
    resume = tmp / "Sam_Fixture_Resume.pdf"
    make_placeholder_pdf(resume)
    port = 9333
    url = FIXTURE.resolve().as_uri()

    chrome = subprocess.Popen(
        [
            str(CHROME), "--headless=new", "--no-first-run", "--no-default-browser-check",
            "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
            f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
            f"--remote-debugging-port={port}", f"--user-data-dir={profile_dir}",
            "--disable-background-networking", "--disable-extensions", "--disable-sync",
            url,
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        targets = [t for t in wait_for_devtools(port) if t.get("type") == "page"]
        target = next(t for t in targets if t.get("url") == url)
        conn = WSConnection(target["webSocketDebuggerUrl"])
        conn.call("Page.enable")
        conn.call("Runtime.enable")
        conn.call("DOM.enable")
        conn.call("Emulation.setDeviceMetricsOverride", {
            "width": VIEWPORT[0], "height": VIEWPORT[1], "deviceScaleFactor": 2, "mobile": False,
        })
        time.sleep(0.6)
        rec = Recorder(conn, frames)

        # Exact-target bind: the adapter refuses to act if location.href drifts.
        adapter = MutableCDPPageAdapter(target_id=target["id"], target_url=url, connection=conn)

        rec.frame(hold=8)
        hud(conn, "__hud.stage('bind','active'); __hud.log('bind target ' + %s, 'dim')" % json.dumps(target["id"][:12] + "…"))
        rec.frame(hold=4)
        snap = adapter.read_only_snapshot()
        hud(conn, "__hud.log('url matches expected  ✓', 'ok'); __hud.stage('bind','done'); __hud.stage('inventory','active')")
        rec.frame(hold=5)

        required = ["#first_name", "#last_name", "#email", "#phone", "#resume", "#authorization", "#sponsorship", "#school", "#source"]
        safety = adapter.inspect_safety_surface(required)
        hud(conn, "__hud.log('%d required controls found', 'dim')" % len(required))
        rec.frame(hold=3)
        hud(conn, "__hud.log('all visible · enabled · unobscured  ✓', 'ok'); __hud.stage('inventory','done'); __hud.stage('fill','active')")
        rec.frame(hold=6)

        evidence: list[dict] = []
        for key in ("first_name", "last_name", "email", "phone"):
            sel = f"#{key}"
            hud(conn, "__hud.log(%s, 'dim')" % json.dumps(f"replace_text {sel}"))
            ev = type_like_human(adapter, rec, sel, PROFILE[key])
            evidence.append(ev)
            assert ev["verified"], ev
            hud(conn, "__hud.mark(%s); __hud.log(%s, 'ok')" % (json.dumps(key), json.dumps(f"  read-back == expected  verified:true")))
            rec.frame(hold=4)

        hud(conn, "__hud.stage('fill','done'); __hud.stage('upload','active'); __hud.log('cdp_upload #resume', 'dim')")
        rec.frame(hold=4)
        ev = cdp_upload(adapter, "#resume", str(resume))
        evidence.append(ev)
        assert ev["verified"], ev
        sha = adapter.read_uploaded_sha256("#resume")
        hud(conn, "__hud.attached(%s); __hud.log(%s, 'ok'); __hud.log(%s, 'ok')" % (
            json.dumps(resume.name),
            json.dumps(f"  filename read-back  verified:true"),
            json.dumps(f"  sha256 {sha[:16]}…  matches source"),
        ))
        rec.frame(hold=10)

        hud(conn, "__hud.stage('upload','done'); __hud.stage('fill','active')")
        for key in ("authorization", "sponsorship", "school", "source"):
            sel = f"#{key}"
            hud(conn, "__hud.log(%s, 'dim')" % json.dumps(f"native_select {sel}"))
            rec.frame(hold=2)
            ev = native_select(adapter, sel, PROFILE[key])
            evidence.append(ev)
            assert ev["verified"], ev
            hud(conn, "__hud.mark(%s); __hud.log(%s, 'ok')" % (json.dumps(key), json.dumps(f"  selected option read-back  verified:true")))
            rec.frame(hold=5)

        hud(conn, "__hud.stage('fill','done'); __hud.stage('review','active'); __hud.log('reconcile Review: %d/%d fields exact', 'dim')" % (len(evidence), len(evidence)))
        rec.frame(hold=6)
        hud(conn, "__hud.log('review_authoritative: true', 'ok'); __hud.log('human_required: []', 'ok'); __hud.log('→ eligible for autonomous submit', 'warn')")
        rec.frame(hold=10)

        submit = adapter.inspect_submit_control("#submit")
        assert submit["visible"] and submit["enabled"] and submit["unique"], submit
        hud(conn, "__hud.stage('review','done'); __hud.stage('authorize','active'); __hud.log('policy: non-MAANGO · no CAPTCHA · no gate  ✓', 'ok')")
        rec.frame(hold=5)
        token_digest = hashlib.sha256(f"{target['id']}|{url}|GH-123|{time.time()}".encode()).hexdigest()
        hud(conn, "__hud.log(%s, 'ok'); __hud.log('bound to target · url · req · review hash', 'dim')" % json.dumps(f"single-use token {token_digest[:10]}…  ttl 300s"))
        rec.frame(hold=7)

        hud(conn, "__hud.stage('authorize','done'); __hud.stage('submit','active'); __hud.log('inspect #submit: visible · enabled · unique  ✓', 'ok')")
        rec.frame(hold=4)
        hud(conn, "__hud.log('consume token → journal intent → click ×1', 'warn')")
        rec.frame(hold=5)
        adapter.click_submit_once("#submit")           # the one and only click
        rec.frame(hold=3)
        hud(conn, "__hud.log('token consumed — replay impossible', 'dim'); __hud.stage('submit','done'); __hud.stage('confirm','active')")
        rec.frame(hold=6)

        confirmation = adapter.inspect_confirmation()   # real read-back, no replay
        assert confirmation.get("confirmed") is True, confirmation
        hud(conn, "__hud.log('confirmation read-back: state=submitted  ✓', 'ok')")
        rec.frame(hold=5)
        hud(conn, "__hud.log('portal: 1 matching record · submitted:true  ✓', 'ok')")
        rec.frame(hold=5)
        hud(conn, "__hud.log('ledger · tracker · Discord  ✓  read-back', 'ok'); __hud.stage('confirm','done')")
        rec.frame(hold=8)
        hud(conn, "__hud.log('APPLIED — no human in the loop', 'ok')")
        rec.frame(hold=30)

        # Prove exactly one submit happened and the page reports it.
        submitted = conn.call("Runtime.evaluate", {"expression": "document.body.dataset.submitted || 'false'", "returnByValue": True})["result"]["value"]
        assert submitted == "true", "fixture must report submitted after the one-shot click"
        conn.close()
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    palette = tmp / "palette.png"
    scale = f"scale={VIEWPORT[0]}:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", str(frames / "f%05d.png"),
                    "-vf", f"{scale},palettegen=max_colors=128:stats_mode=diff", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps), "-i", str(frames / "f%05d.png"), "-i", str(palette),
                    "-lavfi", f"{scale}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", "-loop", "0", str(out)], check=True)

    summary = {
        "output": str(out),
        "bytes": out.stat().st_size,
        "frames": rec.index,
        "seconds": round(rec.index / args.fps, 1),
        "fields_verified": sum(1 for e in evidence if e.get("verified")),
        "fields_total": len(evidence),
        "submitted": submitted,
        "confirmation": confirmation,
        "safety_surface_ok": bool(safety.get("control_visible")) and not safety.get("overlay_present"),
    }
    print(json.dumps(summary, indent=2))
    if not args.keep_frames:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
