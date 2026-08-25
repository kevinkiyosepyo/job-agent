from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import credential_adapter


def test_resolve_keychain_reference_checks_metadata_without_exposing_a_secret():
    calls: list[list[str]] = []

    def run_keychain(command: list[str]) -> int:
        calls.append(command)
        return 0

    result = credential_adapter.resolve_keychain_reference(
        service="approved-njoyn-service",
        account="candidate@example.test",
        approved_services={"approved-njoyn-service"},
        run_keychain=run_keychain,
    )

    assert calls == [[
        "security",
        "find-generic-password",
        "-s",
        "approved-njoyn-service",
        "-a",
        "candidate@example.test",
    ]]
    assert result == {
        "available": True,
        "service": "approved-njoyn-service",
        "account": "candidate@example.test",
        "secret_access": "runtime_only",
    }
    assert "-w" not in calls[0]
    assert "password" not in result


def test_resolve_keychain_reference_rejects_unapproved_service_without_keychain_access():
    with pytest.raises(ValueError, match="unapproved credential service"):
        credential_adapter.resolve_keychain_reference(
            service="unknown-service",
            account="candidate@example.test",
            approved_services={"approved-njoyn-service"},
            run_keychain=lambda _: pytest.fail("must not access Keychain"),
        )
