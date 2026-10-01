"""Bounded CAPTCHA attempt: exact target, response evidence, never bypass a gate."""
import pytest

import captcha_solver


class FakeCDP:
    def __init__(self, *, kind="recaptcha_v2", states=(False, True), url="https://example.test/apply", checkbox=True):
        self.kind, self.states, self.url, self.checkbox = kind, list(states), url, checkbox
        self.calls = []

    def call(self, method, params):
        self.calls.append((method, params))
        if method == "Runtime.evaluate":
            expression = params["expression"]
            if expression == "location.href":
                value = self.url
            elif "_captcha_probe" in expression:
                value = {"detected": True, "kind": self.kind, "cleared": self.states.pop(0) if len(self.states) > 1 else self.states[0]}
            elif "_captcha_checkbox" in expression:
                value = {"found": self.checkbox, "x": 42, "y": 60}
            else:
                raise AssertionError("unexpected evaluation")
            return {"result": {"value": value}}
        if method == "Input.dispatchMouseEvent":
            return {}
        raise AssertionError("unexpected CDP call")


def test_exact_target_checkbox_click_requires_postclick_token():
    conn = FakeCDP()
    result = captcha_solver.attempt_solve(conn, expected_url=conn.url, timeout=0.03, poll_interval=0)
    assert result["solved"] is True
    assert [p["type"] for m, p in conn.calls if m == "Input.dispatchMouseEvent"] == ["mousePressed", "mouseReleased"]


@pytest.mark.parametrize("kind,states,checkbox", [
    ("recaptcha_v2", [False], True),
    ("recaptcha_v2", [False], False),
    ("unknown_checkbox", [False], True),
    ("recaptcha_invisible", [False], True),
])
def test_unresolved_or_unsupported_challenge_never_claims_success(kind, states, checkbox):
    conn = FakeCDP(kind=kind, states=states, checkbox=checkbox)
    result = captcha_solver.attempt_solve(conn, expected_url=conn.url, timeout=0.01, poll_interval=0)
    assert result["solved"] is False
    if not checkbox or kind in ("unknown_checkbox", "recaptcha_invisible"):
        assert not any(method == "Input.dispatchMouseEvent" for method, _ in conn.calls)


def test_changed_target_never_receives_click():
    conn = FakeCDP()
    result = captcha_solver.attempt_solve(conn, expected_url="https://example.test/other", timeout=0.01, poll_interval=0)
    assert result["solved"] is False
    assert not any(method == "Input.dispatchMouseEvent" for method, _ in conn.calls)


def test_backend_captcha_attempt_only_on_exact_gated_target(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate, FakeWorker
    from test_one_page_production import HTML
    import schonfeld_form
    import captcha_solver as solver
    client = FakeWorker()
    attempts = []
    class Page:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read_only_snapshot(self):
            return {"read_only": True, "target_id": "new-target", "url": schonfeld_form.URL,
                    "html": HTML.replace("</html>", "<p>Please complete CAPTCHA</p></html>")}
    class Transport:
        def bind_page_target(self, target_id):
            assert target_id == "new-target"
            return Page()
    class Bound:
        target_url = schonfeld_form.URL
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class CDPTransport:
        def bind_page_target(self, target_id):
            attempts.append(target_id)
            return Bound()
    backend, job = backend_with_candidate(tmp_path, client=client, transport_builder=lambda *a, **k: Transport())
    monkeypatch.setattr(solver, "attempt_solve", lambda *a, **k: {"solved": False, "detail": "challenge_not_cleared"})
    backend._captcha_transport_factory = lambda _: CDPTransport()
    with pytest.raises(Exception) as blocked:
        backend.prepare(job, lambda **_: None)
    assert attempts == ["new-target"], str(blocked.value)
    assert getattr(blocked.value, 'state', None) == 'blocked_security'


def test_backend_requires_fresh_worker_gate_free_readback(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form
    import captcha_solver

    backend, job = backend_with_candidate(tmp_path)
    gated = HTML.replace('</html>', '<p>Please complete CAPTCHA</p></html>')
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': gated}
    reads = []
    class Page:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read_only_snapshot(self):
            reads.append(True)
            return {**snapshot, 'html': HTML if len(reads) == 1 else gated}
    class Transport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Page()
    class Bound:
        target_url = target['url']
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class CDPTransport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Bound()
    backend._captcha_transport_factory = lambda _: CDPTransport()
    backend._transport = lambda *a, **k: Transport()
    monkeypatch.setattr(captcha_solver, 'attempt_solve', lambda *a, **k: {'solved': True, 'kind': 'recaptcha_v2'})
    monkeypatch.setattr(captcha_solver, 'detect', lambda *a, **k: {'detected': True, 'kind': 'recaptcha_v2', 'cleared': True})
    monkeypatch.setattr(captcha_solver, '_value', lambda *a, **k: target['url'])
    fresh = backend._try_captcha_on_new_target(job, target, snapshot)
    assert fresh['html'] == HTML
    assert reads == [True]
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'
    assert len(reads) == 2


def test_fresh_iframe_only_other_provider_blocks_after_token(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form
    import captcha_solver

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'],
                'html': HTML.replace('</html>', '<p>Please complete CAPTCHA</p></html>')}
    fresh = {**snapshot, 'html': HTML.replace('</html>',
        '<iframe src="https://challenges.cloudflare.com/cdn-cgi/challenge-platform"></iframe></html>')}
    class Page:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read_only_snapshot(self): return fresh
    class Bound:
        target_url = target['url']
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class Transport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Bound()
    class WorkerTransport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Page()
    backend._captcha_transport_factory = lambda _: Transport()
    backend._transport = lambda *a, **k: WorkerTransport()
    monkeypatch.setattr(captcha_solver, 'attempt_solve', lambda *a, **k: {'solved': True, 'kind': 'recaptcha_v2'})
    monkeypatch.setattr(captcha_solver, 'detect', lambda *a, **k: {'detected': True, 'kind': 'turnstile', 'cleared': False})
    monkeypatch.setattr(captcha_solver, '_value', lambda *a, **k: target['url'])
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'


def test_captcha_uses_validated_configured_chrome_endpoint(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form
    import captcha_solver

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'],
                'html': HTML.replace('</html>', '<p>Please complete CAPTCHA</p></html>')}
    received = []
    class Bound:
        target_url = target['url']
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class Transport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Bound()
    def factory(base_url):
        received.append(base_url)
        return Transport()
    backend._captcha_transport_factory = factory
    monkeypatch.setattr(captcha_solver, 'attempt_solve', lambda *a, **k: {'solved': False})
    backend.config['captcha_cdp_base_url'] = 'http://127.0.0.1:18800'
    with pytest.raises(CandidateParked):
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert received == ['http://127.0.0.1:18800']
    received.clear()
    backend.config['captcha_cdp_base_url'] = 'https://not-loopback.example:18800'
    with pytest.raises(CandidateParked):
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert received == []


def test_provider_frame_without_visible_label_is_attempted_but_unresolved_is_blocked(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form
    import captcha_solver

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    html = HTML.replace('</html>', '<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe></html>')
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': html}
    attempts = []
    class Bound:
        target_url = target['url']
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class Transport:
        def bind_page_target(self, target_id):
            attempts.append(target_id)
            return Bound()
    backend._captcha_transport_factory = lambda _: Transport()
    monkeypatch.setattr(captcha_solver, 'attempt_solve', lambda *a, **k: {'solved': False, 'detail': 'challenge_not_cleared'})
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'
    assert attempts == [target['id']]


def test_hidden_provider_plumbing_is_not_a_blocker(tmp_path, monkeypatch):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    import schonfeld_form
    import captcha_solver

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    html = HTML.replace('</html>', '<iframe hidden src="https://www.google.com/recaptcha/api2/anchor"></iframe></html>')
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': html}
    class Bound:
        target_url = target['url']
        _connection = object()
        def __enter__(self): return self
        def __exit__(self, *_): pass
    class Transport:
        def bind_page_target(self, target_id):
            assert target_id == target['id']
            return Bound()
    backend._captcha_transport_factory = lambda _: Transport()
    monkeypatch.setattr(captcha_solver, 'attempt_solve',
                        lambda *a, **k: {'solved': False, 'kind': None, 'detail': 'no_visible_widget'})
    assert backend._try_captcha_on_new_target(job, target, snapshot) is snapshot


def test_mixed_captcha_and_mfa_never_clicks(tmp_path):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    html = HTML.replace('</html>', '<p>Please complete CAPTCHA</p><p>Approve the sign-in request on your phone</p></html>')
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': html}
    attempts = []
    backend._captcha_transport_factory = lambda _: attempts.append('bound')
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'
    assert attempts == []


@pytest.mark.parametrize('other_prompt', [
    'Verify your email to continue',
    'Take the skills test assessment to continue',
])
def test_mixed_captcha_and_other_manual_gate_never_clicks(tmp_path, other_prompt):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    html = HTML.replace('</html>', f'<p>Please complete CAPTCHA</p><p>{other_prompt}</p></html>')
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': html}
    attempts = []
    backend._captcha_transport_factory = lambda _: attempts.append('bound')
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'
    assert attempts == []


def test_initial_worker_reported_mfa_gate_never_clicks(tmp_path):
    from test_autonomous_backend import backend_with_candidate
    from test_one_page_production import HTML
    from autonomous_controller import CandidateParked
    import schonfeld_form

    backend, job = backend_with_candidate(tmp_path)
    target = {'id': 'new-target', 'url': schonfeld_form.URL}
    html = HTML.replace('</html>', '<p>Please complete CAPTCHA</p></html>')
    snapshot = {'read_only': True, 'target_id': target['id'], 'url': target['url'], 'html': html,
                'gates': [{'type': 'captcha'}, {'type': 'mfa_approval'}]}
    attempts = []
    backend._captcha_transport_factory = lambda _: attempts.append('bound')
    with pytest.raises(CandidateParked) as blocked:
        backend._try_captcha_on_new_target(job, target, snapshot)
    assert blocked.value.state == 'blocked_security'
    assert attempts == []


@pytest.mark.parametrize('kind', ['hcaptcha', 'turnstile'])
def test_non_recaptcha_provider_never_receives_click(kind):
    conn = FakeCDP(kind=kind, states=(False, True))
    result = captcha_solver.attempt_solve(conn, expected_url=conn.url, timeout=0.03, poll_interval=0)
    assert result['solved'] is False
    assert not any(method == 'Input.dispatchMouseEvent' for method, _ in conn.calls)


def test_protocol_relative_recaptcha_frame_is_inspected():
    assert captcha_solver.has_provider_frame('<iframe src="//www.google.com/recaptcha/api2/anchor"></iframe>')


@pytest.mark.parametrize('states', [(False, True), (True,)])
def test_managed_turnstile_never_receives_click(states):
    conn = FakeCDP(kind='turnstile', states=states)
    result = captcha_solver.attempt_solve(conn, expected_url=conn.url, timeout=0.03, poll_interval=0)
    assert result['solved'] is False
    assert not any(method == 'Input.dispatchMouseEvent' for method, _ in conn.calls)
