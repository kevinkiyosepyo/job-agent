"""Conservative classification of visible security prompts on ATS pages.

Static text is a blocker candidate, not evidence that verification succeeded.
Callers must re-inspect the actual page after a user or authorized OTP flow
has completed; never treat a challenge as cleared by removing its label.
"""
from __future__ import annotations

import re


def detect_security_gates(text_chunks: list[str]) -> list[dict[str, str]]:
    """Return every visible-text security cue, not just the first priority match."""
    text = " ".join(text_chunks).casefold()
    candidates = (
        ("captcha", r"\b(?:captcha|hcaptcha|recaptcha|turnstile)\b", "CAPTCHA challenge detected"),
        ("passkey", r"\b(?:passkey|touch id|face id|security key|webauthn)\b", "Passkey or device-authentication prompt detected"),
        ("mfa_approval", r"\b(?:mfa|multi.factor authentication|two.factor authentication|authenticator app|approve (?:the |your )?(?:sign.in|login|request)|push notification|device approval)\b", "MFA approval prompt detected"),
        ("identity_verification", r"\b(?:identity verification|verify your identity|government (?:issued )?id|photo id)\b", "Identity verification required"),
    )
    return [{"type": kind, "detail": detail} for kind, pattern, detail in candidates
            if re.search(pattern, text)]


def detect_security_gate(text_chunks: list[str]) -> dict[str, str] | None:
    gates = detect_security_gates(text_chunks)
    return gates[0] if gates else None
