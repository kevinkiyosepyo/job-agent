"""Optional macOS Keychain setup; this module never serializes a password.

Store setup_credentials(email)'s result at profile['credentials']:
    {
        'universal': {'service': 'hermes-job-agent-universal', 'account': email},
        'workday': {'service': 'hermes-job-agent-workday-universal', 'account': email},
    }
An empty result means skipped, cancelled, or failed: preserve an existing profile
rather than treating it as a request to delete saved references.

At runtime, credential_reference(profile, 'workday') validates/copies a reference
without accessing secrets. In the authorized login process only, use the explicit
keyring.backends.macOS.Keyring().get_password(ref['service'], ref['account']);
keep the result in memory and never print it. A reference does not prove a portal
login succeeds. Reuse verifies both Keychain entries exist and are readable.

There is no CLI password argument, environment-password lookup, or file fallback.
Injected backend/password_fn are for trusted integrations and offline tests only;
a custom password_fn must provide hidden input, never input() or echoed input.
"""

import getpass
import re
import sys
import warnings


SERVICES = {
    "universal": "hermes-job-agent-universal",
    "workday": "hermes-job-agent-workday-universal",
}


def _valid_account(account):
    return isinstance(account, str) and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", account) is not None


def credential_reference(profile, kind="workday"):
    """Return a validated secret-free reference (or {}); never read Keychain."""
    if not isinstance(profile, dict) or not isinstance(kind, str) or kind not in SERVICES:
        return {}
    credentials = profile.get("credentials")
    if not isinstance(credentials, dict):
        return {}
    reference = credentials.get(kind)
    if not isinstance(reference, dict) or reference.get("service") != SERVICES[kind]:
        return {}
    contact = profile.get("contact")
    if (not isinstance(contact, dict) or not _valid_account(reference.get("account"))
            or reference["account"] != contact.get("email")):
        return {}
    return {"service": reference["service"], "account": reference["account"]}


def setup_credentials(account, *, input_fn=input, output_fn=print,
                      password_fn=None, backend=None):
    """Return credential references, or an empty dict when setup is skipped."""
    try:
        return _setup_credentials(account, input_fn, output_fn, password_fn, backend)
    except (EOFError, KeyboardInterrupt):
        output_fn("Credential setup cancelled. If a write was interrupted, records "
                  "may already be saved; review Keychain before retrying.")
        return {}
    except Exception:
        # Never render exception text or traceback: a backend may include secrets.
        output_fn("Credential setup failed. Some records may already be saved; "
                  "review Keychain before retrying. No references were returned.")
        return {}


def _setup_credentials(account, input_fn, output_fn, password_fn, backend):
    output_fn("Credential setup is optional; skip is the default.")
    output_fn("Password reuse increases risk across portals. Use a dedicated job-only "
              "password; never reuse your email or banking password.")
    choice = input_fn("[s]kip (default), [r]euse existing, or [n]ew shared password: ").strip().lower()
    if choice not in {"n", "r"}:
        return {}
    if not _valid_account(account):
        output_fn("Supply your own valid email address; credential setup skipped.")
        return {}
    if backend is None:
        if sys.platform != "darwin":
            output_fn("Credential storage requires macOS Keychain; setup skipped. "
                      "No plaintext fallback is available.")
            return {}
        # Bypass keyring.get_keyring(): user/plugin discovery can select plaintext.
        try:
            from keyring.backends.macOS import Keyring
        except ImportError:
            output_fn("Install requirements.txt to enable keyring's macOS Keychain "
                      "backend; setup skipped. No plaintext fallback is available.")
            return {}
        backend = Keyring()
    existing = {service: backend.get_password(service, account)
                for service in SERVICES.values()}
    if choice == "r":
        if not all(isinstance(value, str) and value for value in existing.values()):
            output_fn("Existing credentials are missing or empty; set a new shared password instead.")
            return {}
        return {kind: {"service": service, "account": account}
                for kind, service in SERVICES.items()}
    for service, value in existing.items():
        if value is not None:
            confirm = input_fn(f"Overwrite existing {service}? Type yes (default no): ")
            if confirm.strip().lower() != "yes":
                output_fn("Existing credentials unchanged; setup skipped.")
                return {}
    if password_fn is None:
        password_fn = getpass.getpass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = password_fn("New job-only password (hidden): ")
            confirmation = password_fn("Confirm password (hidden): ")
    except getpass.GetPassWarning:
        output_fn("Secure hidden input is unavailable; nothing was saved. "
                  "Retry in an interactive terminal; echo fallback is not allowed.")
        return {}
    if password != confirmation:
        output_fn("Passwords do not match; nothing was saved.")
        return {}
    if not (len(password) >= 12 and any(c.isupper() for c in password)
            and any(c.islower() for c in password) and any(c.isdigit() for c in password)
            and any(not c.isalnum() and not c.isspace() for c in password)):
        output_fn("Use at least 12 characters with uppercase, lowercase, a digit, "
                  "and a symbol; nothing was saved.")
        return {}
    references = {}
    for kind, service in SERVICES.items():
        backend.set_password(service, account, password)
        if backend.get_password(service, account) != password:
            output_fn("Keychain verification failed. Some records may already be saved; "
                      "review Keychain before retrying. No references were returned.")
            return {}
        references[kind] = {"service": service, "account": account}
    return references
