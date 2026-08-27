"""Explicit, secret-free runtime session gates for live ATS execution."""
from __future__ import annotations


def plan_authenticated_session(tenant_session: dict[str, object]) -> dict[str, object]:
    """Return session reuse or a human-only login/identity-verification gate."""
    tenant = tenant_session.get("tenant")
    authenticated = tenant_session.get("authenticated")
    reference = tenant_session.get("session_reference")
    if not isinstance(tenant, str) or not tenant:
        raise ValueError("tenant session requires a tenant")
    if not isinstance(authenticated, bool):
        raise ValueError("tenant session requires authenticated state")
    if not isinstance(reference, str) or not reference.startswith("runtime-only:"):
        raise ValueError("tenant session requires a runtime-only reference")
    return {
        "tenant": tenant,
        "authenticated": authenticated,
        "session_reference": reference,
        "next_gate": (
            "authenticated_session_reuse"
            if authenticated
            else "login_or_identity_verification_required"
        ),
        "credential_serialized": False,
    }
