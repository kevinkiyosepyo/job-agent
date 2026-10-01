"""Security challenges must never disappear just because a solver module exists."""
import pytest

import greenhouse_handler
import lever_handler
import workday_handler

URLS = [
    (greenhouse_handler, "https://job-boards.greenhouse.io/example/jobs/123"),
    (lever_handler, "https://jobs.lever.co/example/123/apply"),
    (workday_handler, "https://example.wd1.myworkdayjobs.com/en-US/careers/job/123"),
]


@pytest.mark.parametrize("handler,url", URLS)
@pytest.mark.parametrize("prompt,kind", [
    ("Use your passkey to sign in", "passkey"),
    ("Approve the sign-in request on your phone", "mfa_approval"),
    ("Complete identity verification to continue", "identity_verification"),
    ("Please complete the visible hCaptcha challenge", "captcha"),
])
def test_unresolved_security_challenge_blocks_preparation(handler, url, prompt, kind):
    html = f'<h1>Software Engineer Intern</h1><form><input name="full_name" required></form><p>{prompt}</p>'
    result = handler.inspect_html(html, page_url=url)
    assert result["manual_gate"]["type"] == kind
    if handler is lever_handler:
        from prepare_job import prepare_saved_html
        assert prepare_saved_html(html_text=html, page_url=url)["submission_enabled"] is False
    else:
        assert result["safe_to_prepare"] is False


def test_ordinary_email_otp_prompt_remains_blocked_until_verified():
    html = '<h1>Software Engineer Intern</h1><form><input name="email_code"></form><p>Verify your email to continue</p>'
    result = greenhouse_handler.inspect_html(html, page_url=URLS[0][1])
    assert result["manual_gate"]["type"] == "email_verification"
    assert result["safe_to_prepare"] is False


def test_dormant_captcha_script_is_not_a_visible_challenge():
    html = '<h1>Software Engineer Intern</h1><form><input name="full_name"></form><script>var recaptcha = true;</script>'
    result = greenhouse_handler.inspect_html(html, page_url=URLS[0][1])
    assert result["manual_gate"] is None


def test_security_gate_enumeration_keeps_simultaneous_challenges():
    from security_gates import detect_security_gates
    found = detect_security_gates(['Please complete CAPTCHA', 'Approve the sign-in request on your phone'])
    assert [gate['type'] for gate in found] == ['captcha', 'mfa_approval']
