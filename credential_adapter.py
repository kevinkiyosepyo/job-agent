"""Secret-free runtime Keychain reference contract for ATS account flows."""
from __future__ import annotations

import subprocess
from collections.abc import Callable, Collection, Sequence


KeychainRunner = Callable[[list[str]], int]


def _macos_keychain_metadata(command: list[str]) -> int:
    """Check generic-password item presence without requesting its value."""
    completed = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode


def resolve_keychain_reference(
    *,
    service: str,
    account: str,
    approved_services: Collection[str],
    run_keychain: KeychainRunner = _macos_keychain_metadata,
) -> dict[str, str | bool]:
    """Return secret-free availability metadata for an approved Keychain item.

    This deliberately invokes ``security find-generic-password`` without ``-w``;
    callers receive a runtime-only reference, never a credential value.
    """
    if service not in approved_services:
        raise ValueError("unapproved credential service")
    if not account:
        raise ValueError("credential account is required")

    available = run_keychain([
        "security",
        "find-generic-password",
        "-s",
        service,
        "-a",
        account,
    ]) == 0
    return {
        "available": available,
        "service": service,
        "account": account,
        "secret_access": "runtime_only",
    }
