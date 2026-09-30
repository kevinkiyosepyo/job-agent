"""Offline-only credential setup tests; never access the real Keychain."""

import pytest

ACCOUNT = "applicant@example.test"
SERVICES = {
    "universal": "hermes-job-agent-universal",
    "workday": "hermes-job-agent-workday-universal",
}
PASSWORD = "Example-only-42!"


class MemoryBackend:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.events = []

    def get_password(self, service, account):
        self.events.append(("get", service, account))
        return self.values.get((service, account))

    def set_password(self, service, account, password):
        self.events.append(("set", service, account))
        self.values[service, account] = password


def answers(*values):
    iterator = iter(values)
    return lambda prompt: next(iterator)


def expected_references():
    return {kind: {"service": service, "account": ACCOUNT}
            for kind, service in SERVICES.items()}


def test_new_shared_password_is_verified_and_returns_only_references():
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend()
    messages = []
    result = setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(PASSWORD, PASSWORD), backend=backend,
    )
    assert result == expected_references()
    assert backend.values == {(service, ACCOUNT): PASSWORD for service in SERVICES.values()}
    for service in SERVICES.values():
        assert ("get", service, ACCOUNT) in backend.events[backend.events.index(("set", service, ACCOUNT)) + 1:]
    text = " ".join(messages).lower()
    assert "reuse" in text and "risk" in text
    assert "dedicated job-only" in text and "email" in text and "banking" in text
    assert PASSWORD not in repr(result) + repr(messages)


def test_confirmation_mismatch_never_writes():
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend()
    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(PASSWORD, "Different-only-42!"), backend=backend,
    ) == {}
    assert not backend.values
    assert "match" in " ".join(messages).lower()
    assert PASSWORD not in repr(messages)


@pytest.mark.parametrize("weak", [
    "Short-42!", "all-lowercase-42!", "ALL-UPPERCASE-42!",
    "No-digits-here!", "NoSymbolsHere42", "WhitespaceOnly42 ", "",
])
def test_weak_password_never_writes(weak):
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend()
    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(weak, weak), backend=backend,
    ) == {}
    assert not backend.values
    assert "12" in " ".join(messages)


@pytest.mark.parametrize("failed_service", list(SERVICES.values()))
def test_readback_mismatch_never_reports_success(failed_service):
    from onboarding_credentials import setup_credentials

    class BrokenReadback(MemoryBackend):
        def set_password(self, service, account, password):
            super().set_password(service, account, password)
            if service == failed_service:
                self.values[service, account] = "unexpected-value"

    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(PASSWORD, PASSWORD), backend=BrokenReadback(),
    ) == {}
    text = " ".join(messages).lower()
    assert "verif" in text and "may" in text and "saved" in text
    assert PASSWORD not in text and "unexpected-value" not in text


@pytest.mark.parametrize("confirmations", [("",), ("yes", "")])
def test_existing_records_need_separate_explicit_confirmation_before_any_write(confirmations):
    from onboarding_credentials import setup_credentials

    original = {(service, ACCOUNT): PASSWORD for service in SERVICES.values()}
    backend = MemoryBackend(original)
    prompts = []
    responses = answers("n", *confirmations)

    def ask(prompt):
        prompts.append(prompt)
        return responses(prompt)

    assert setup_credentials(
        ACCOUNT, input_fn=ask, output_fn=lambda message: None,
        password_fn=answers("New-example-42!", "New-example-42!"), backend=backend,
    ) == {}
    assert backend.values == original
    assert not any(event[0] == "set" for event in backend.events)
    assert SERVICES["universal"] in prompts[1]
    if len(confirmations) == 2:
        assert SERVICES["workday"] in prompts[2]


def test_reuse_checks_both_existing_records_without_writing_or_prompting_password():
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend({(service, ACCOUNT): PASSWORD for service in SERVICES.values()})
    assert setup_credentials(
        ACCOUNT, input_fn=answers("r"), output_fn=lambda message: None,
        password_fn=answers(), backend=backend,
    ) == expected_references()
    assert backend.events == [("get", service, ACCOUNT) for service in SERVICES.values()]


@pytest.mark.parametrize("missing", [None, ""])
def test_reuse_refuses_missing_or_empty_records(missing):
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend({(SERVICES["universal"], ACCOUNT): PASSWORD,
                             (SERVICES["workday"], ACCOUNT): missing})
    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("r"), output_fn=messages.append,
        password_fn=answers(), backend=backend,
    ) == {}
    assert "missing" in " ".join(messages).lower()
    assert not any(event[0] == "set" for event in backend.events)


@pytest.mark.parametrize("fail_at", range(6))
def test_backend_errors_are_redacted_at_every_read_or_write(fail_at, capsys, caplog):
    from onboarding_credentials import setup_credentials

    class FailingBackend(MemoryBackend):
        def check(self):
            if len(self.events) == fail_at:
                raise RuntimeError("backend leaked " + PASSWORD)

        def get_password(self, service, account):
            self.check()
            return super().get_password(service, account)

        def set_password(self, service, account, password):
            self.check()
            super().set_password(service, account, password)

    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(PASSWORD, PASSWORD), backend=FailingBackend(),
    ) == {}
    captured = capsys.readouterr()
    assert PASSWORD not in repr(messages) + captured.out + captured.err + caplog.text
    assert "failed" in " ".join(messages).lower()


def test_default_password_reader_uses_getpass_twice(monkeypatch):
    import getpass
    from onboarding_credentials import setup_credentials

    prompts = []

    def hidden(prompt):
        prompts.append(prompt)
        return PASSWORD

    monkeypatch.setattr(getpass, "getpass", hidden)
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=lambda message: None,
        backend=MemoryBackend(),
    ) == expected_references()
    assert len(prompts) == 2
    assert "confirm" in prompts[1].lower()


@pytest.mark.parametrize("warn_at", [0, 1])
@pytest.mark.parametrize("injected", [False, True])
def test_getpass_warning_fails_closed_before_echo_fallback(monkeypatch, capsys, warn_at, injected):
    import getpass
    import warnings
    from onboarding_credentials import setup_credentials

    prompts = []
    fallback = []

    def hidden(prompt):
        if len(prompts) == warn_at:
            warnings.warn("echo fallback " + PASSWORD, getpass.GetPassWarning)
            fallback.append(True)
        prompts.append(prompt)
        return PASSWORD

    monkeypatch.setattr(getpass, "getpass", hidden)
    backend = MemoryBackend()
    messages = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = setup_credentials(
            ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
            password_fn=hidden if injected else None, backend=backend,
        )
    assert result == {}
    assert not fallback and not backend.values
    assert "hidden" in " ".join(messages).lower()
    captured = capsys.readouterr()
    assert PASSWORD not in repr(messages) + captured.out + captured.err


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_nonmacos_explains_unsupported_secure_storage_without_prompting(monkeypatch, platform):
    import sys
    from onboarding_credentials import setup_credentials

    monkeypatch.setattr(sys, "platform", platform)
    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(),
    ) == {}
    text = " ".join(messages).lower()
    assert "macos keychain" in text and "no plaintext" in text


def test_default_backend_is_explicit_macos_keyring_not_plugin_autodiscovery(monkeypatch):
    import sys
    from types import ModuleType
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend()
    constructors = []
    package = ModuleType("keyring")
    backends = ModuleType("keyring.backends")
    macos = ModuleType("keyring.backends.macOS")

    def trusted_keyring():
        constructors.append(True)
        return backend

    def forbidden_autodiscovery():
        raise AssertionError("never select a configurable/plaintext backend")

    macos.Keyring = trusted_keyring
    package.get_keyring = forbidden_autodiscovery
    monkeypatch.setitem(sys.modules, "keyring", package)
    monkeypatch.setitem(sys.modules, "keyring.backends", backends)
    monkeypatch.setitem(sys.modules, "keyring.backends.macOS", macos)
    monkeypatch.setattr(sys, "platform", "darwin")
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=lambda message: None,
        password_fn=answers(PASSWORD, PASSWORD),
    ) == expected_references()
    assert constructors == [True]
    assert backend.values == {(service, ACCOUNT): PASSWORD for service in SERVICES.values()}


def test_credential_reference_returns_only_service_account_without_secret_access():
    from onboarding_credentials import credential_reference

    reference = expected_references()["workday"]
    profile = {"contact": {"email": ACCOUNT},
               "credentials": {"workday": {**reference, "password": PASSWORD}}}
    result = credential_reference(profile)
    assert result == reference
    assert PASSWORD not in repr(result)
    result["account"] = "mutated@example.test"
    assert profile["credentials"]["workday"]["account"] == ACCOUNT


@pytest.mark.parametrize("contact", [{}, None, {"email": "different@example.test"}])
def test_reference_is_rejected_when_profile_identity_is_missing_or_changed(contact):
    from onboarding_credentials import credential_reference
    profile = {"contact": contact, "credentials": expected_references()}
    assert credential_reference(profile, "workday") == {}
    assert credential_reference(profile, "universal") == {}


@pytest.mark.parametrize("profile,kind", [
    (None, "workday"), ({}, "workday"), ({"credentials": None}, "workday"),
    ({"credentials": {"workday": "plaintext"}}, "workday"),
    ({"credentials": {"workday": {}}}, "workday"),
    ({"credentials": {"workday": {"service": "untrusted-service", "account": ACCOUNT}}}, "workday"),
    ({"credentials": {"workday": {"service": SERVICES["workday"], "account": ""}}}, "workday"),
    ({"credentials": {"workday": {"service": SERVICES["workday"], "account": "not-email"}}}, "workday"),
    ({"credentials": {"workday": {"service": SERVICES["workday"], "account": [ACCOUNT]}}}, "workday"),
    ({"credentials": expected_references()}, "other"),
    ({"credentials": expected_references()}, []),
])
def test_credential_reference_rejects_malformed_or_untrusted_references(profile, kind):
    from onboarding_credentials import credential_reference

    assert credential_reference(profile, kind) == {}


@pytest.mark.parametrize("account", [None, "", "not-email", " user@example.test", "user@example.test\n"])
def test_invalid_account_never_accesses_backend(account):
    from onboarding_credentials import setup_credentials

    backend = MemoryBackend()
    messages = []
    assert setup_credentials(
        account, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(PASSWORD, PASSWORD), backend=backend,
    ) == {}
    assert not backend.events
    assert "email" in messages[-1].lower()


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
@pytest.mark.parametrize("at_choice", [False, True])
def test_interrupted_prompts_cancel_without_writes(exception, at_choice):
    from onboarding_credentials import setup_credentials

    def interrupted(prompt):
        raise exception(PASSWORD)

    backend = MemoryBackend()
    messages = []
    try:
        result = setup_credentials(
            ACCOUNT, input_fn=interrupted if at_choice else answers("n"),
            output_fn=messages.append, password_fn=interrupted, backend=backend,
        )
    except (EOFError, KeyboardInterrupt):
        result = "interruption escaped"
    assert result == {}
    assert not backend.values
    assert "cancelled" in " ".join(messages).lower()
    assert PASSWORD not in repr(messages)


def test_missing_keyring_explains_dependency_without_plaintext_fallback(monkeypatch):
    import sys
    from onboarding_credentials import setup_credentials

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "keyring.backends.macOS", None)
    messages = []
    assert setup_credentials(
        ACCOUNT, input_fn=answers("n"), output_fn=messages.append,
        password_fn=answers(),
    ) == {}
    text = " ".join(messages).lower()
    assert "install" in text and "requirements.txt" in text
    assert "no plaintext" in text


def test_default_choice_skips_without_backend_or_password_access():
    from onboarding_credentials import setup_credentials

    def forbidden(*args):
        raise AssertionError("skip must not access secrets")

    class NoAccess:
        get_password = forbidden
        set_password = forbidden

    messages = []
    assert setup_credentials(
        "applicant@example.test", input_fn=lambda prompt: "",
        output_fn=messages.append, password_fn=forbidden, backend=NoAccess(),
    ) == {}
    assert any("skip" in message.lower() for message in messages)
