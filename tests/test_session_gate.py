from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_session_gate_reuses_authenticated_runtime_reference_without_serializing_credentials():
    import session_gate

    result = session_gate.plan_authenticated_session(
        {
            "tenant": "cgi",
            "authenticated": True,
            "session_reference": "runtime-only:njoyn-cgi",
        }
    )

    assert result == {
        "tenant": "cgi",
        "authenticated": True,
        "session_reference": "runtime-only:njoyn-cgi",
        "next_gate": "authenticated_session_reuse",
        "credential_serialized": False,
    }


def test_session_gate_stops_at_explicit_login_verification_gate_when_unauthenticated():
    import session_gate

    result = session_gate.plan_authenticated_session(
        {
            "tenant": "cgi",
            "authenticated": False,
            "session_reference": "runtime-only:njoyn-cgi",
        }
    )

    assert result == {
        "tenant": "cgi",
        "authenticated": False,
        "session_reference": "runtime-only:njoyn-cgi",
        "next_gate": "login_or_identity_verification_required",
        "credential_serialized": False,
    }
